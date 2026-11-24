from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import requests

from config import AppConfig, config

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_WEATHER_VARS = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "rain",
    "surface_pressure",
)


class WeatherErrorKind(str, Enum):
    INVALID_COORDINATES = "invalid_coordinates"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"


class WeatherClientError(Exception):
    def __init__(self, kind: WeatherErrorKind, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class WeatherObservation:
    latitude: float
    longitude: float
    observation_time: str | None
    fetched_at_utc: str
    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    rain_mm: float | None = None
    surface_pressure_hpa: float | None = None
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WeatherPollutionNote:
    factor: str
    observed_summary: str
    possible_relationship: str
    caution: str = "Association only; meteorological co-occurrence does not prove causation."


def _to_finite_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if num != num or num in (float("inf"), float("-inf")):
        return None
    return num


class WeatherClient:
    def __init__(
        self,
        app_config: AppConfig = config,
        forecast_url: str = OPEN_METEO_FORECAST_URL,
        session: requests.Session | None = None,
    ) -> None:
        self.config = app_config
        self.forecast_url = forecast_url
        self.session = session or requests.Session()

    def get_current_weather(self, latitude: float | None, longitude: float | None) -> WeatherObservation:
        lat = _to_finite_float(latitude)
        lon = _to_finite_float(longitude)
        if lat is None or lon is None or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise WeatherClientError(
                WeatherErrorKind.INVALID_COORDINATES,
                "Valid latitude [-90, 90] and longitude [-180, 180] are required to fetch weather.",
            )

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(CURRENT_WEATHER_VARS),
            "timezone": "auto",
        }

        try:
            resp = self.session.get(
                self.forecast_url,
                params=params,
                timeout=self.config.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise WeatherClientError(
                WeatherErrorKind.TIMEOUT,
                f"Weather API timed out after {self.config.request_timeout_seconds}s.",
            ) from exc
        except requests.ConnectionError as exc:
            raise WeatherClientError(
                WeatherErrorKind.NETWORK_ERROR,
                "Network error while contacting weather service (independent of WAQI).",
            ) from exc
        except requests.RequestException as exc:
            raise WeatherClientError(
                WeatherErrorKind.NETWORK_ERROR,
                f"Weather request error: {exc}",
            ) from exc

        if resp.status_code >= 400:
            raise WeatherClientError(
                WeatherErrorKind.INVALID_RESPONSE,
                f"Weather API returned HTTP {resp.status_code}.",
                status_code=resp.status_code,
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise WeatherClientError(
                WeatherErrorKind.INVALID_RESPONSE,
                "Weather API returned malformed JSON.",
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("current"), dict):
            raise WeatherClientError(
                WeatherErrorKind.INVALID_RESPONSE,
                "Weather API payload missing 'current' object.",
            )

        cur = payload["current"]
        missing: list[str] = []

        def _get_var(key: str, label: str) -> float | None:
            parsed = _to_finite_float(cur.get(key))
            if parsed is None:
                missing.append(label)
            return parsed

        temp_c = _get_var("temperature_2m", "Temperature")
        hum_pct = _get_var("relative_humidity_2m", "Humidity")
        wind_spd = _get_var("wind_speed_10m", "Wind Speed")
        wind_dir = _get_var("wind_direction_10m", "Wind Direction")
        rain_val = _get_var("rain", "Rainfall")
        press_hpa = _get_var("surface_pressure", "Atmospheric Pressure")

        obs_time_raw = cur.get("time")
        obs_time = obs_time_raw.strip() if isinstance(obs_time_raw, str) and obs_time_raw.strip() else None
        if obs_time is None:
            missing.append("Observation Time")

        return WeatherObservation(
            latitude=lat,
            longitude=lon,
            observation_time=obs_time,
            fetched_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            temperature_c=temp_c,
            humidity_pct=hum_pct,
            wind_speed_kmh=wind_spd,
            wind_direction_deg=wind_dir,
            rain_mm=rain_val,
            surface_pressure_hpa=press_hpa,
            missing_fields=missing,
        )


def analyze_weather_pollution_context(
    weather: WeatherObservation,
    aqi_value: float | int | None = None,
) -> list[WeatherPollutionNote]:
    """
    Generate non-causal meteorological notes alongside air quality readings.
    Explicitly avoids claiming correlation proves causation.
    """
    notes: list[WeatherPollutionNote] = []
    aqi_hint = f" (current AQI reference: {aqi_value})" if aqi_value is not None else ""

    if weather.wind_speed_kmh is not None:
        if weather.wind_speed_kmh < 8.0:
            notes.append(
                WeatherPollutionNote(
                    factor="Wind Speed & Dispersion",
                    observed_summary=f"Light wind speed ({weather.wind_speed_kmh:g} km/h){aqi_hint}",
                    possible_relationship=(
                        "Lower wind speeds are often observed alongside weaker horizontal air dispersion "
                        "and localized pollutant accumulation."
                    ),
                )
            )
        else:
            notes.append(
                WeatherPollutionNote(
                    factor="Wind Speed & Dispersion",
                    observed_summary=f"Moderate/stronger wind speed ({weather.wind_speed_kmh:g} km/h){aqi_hint}",
                    possible_relationship=(
                        "Higher wind speeds often coincide with greater mixing/ventilation or regional "
                        "transport depending on upwind conditions and wind direction."
                    ),
                )
            )

    if weather.wind_direction_deg is not None:
        notes.append(
            WeatherPollutionNote(
                factor="Wind Direction",
                observed_summary=f"Wind bearing {weather.wind_direction_deg:g}°",
                possible_relationship=(
                    "Wind direction indicates the air-mass origin bearing relative to the station "
                    "and helps contextualize upwind vs. downwind readings."
                ),
            )
        )

    if weather.rain_mm is not None:
        if weather.rain_mm > 0.0:
            notes.append(
                WeatherPollutionNote(
                    factor="Rainfall / Wet Scavenging",
                    observed_summary=f"Active rainfall ({weather.rain_mm:g} mm)",
                    possible_relationship=(
                        "Precipitation can coincide with wet removal of airborne particulates and "
                        "surface dust suppression, though timing and intensity vary."
                    ),
                )
            )
        else:
            notes.append(
                WeatherPollutionNote(
                    factor="Rainfall / Dry Conditions",
                    observed_summary="No current rainfall (0 mm)",
                    possible_relationship=(
                        "Dry surface conditions do not provide wet deposition and can coincide with "
                        "resuspended dust when surfaces are dry."
                    ),
                )
            )

    if weather.humidity_pct is not None:
        notes.append(
            WeatherPollutionNote(
                factor="Relative Humidity",
                observed_summary=f"Relative humidity {weather.humidity_pct:g}%",
                possible_relationship=(
                    "Humidity can relate to hygroscopic aerosol growth or boundary-layer moisture "
                    "profiles alongside temperature and emission patterns."
                ),
            )
        )

    if weather.temperature_c is not None or weather.surface_pressure_hpa is not None:
        temp_part = f"{weather.temperature_c:g} °C" if weather.temperature_c is not None else "N/A"
        press_part = (
            f"{weather.surface_pressure_hpa:g} hPa"
            if weather.surface_pressure_hpa is not None
            else "N/A"
        )
        notes.append(
            WeatherPollutionNote(
                factor="Temperature & Surface Pressure",
                observed_summary=f"Temp: {temp_part}, Surface Pressure: {press_part}",
                possible_relationship=(
                    "Temperature and pressure regimes influence boundary-layer stability and secondary "
                    "photochemical/particulate dynamics without establishing direct cause on their own."
                ),
            )
        )

    return notes