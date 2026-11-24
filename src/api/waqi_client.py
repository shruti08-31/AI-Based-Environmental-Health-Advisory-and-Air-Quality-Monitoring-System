from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import requests

from config import AppConfig, config

WAQI_BASE_URL = "https://api.waqi.info"
POLLUTANT_KEYS: tuple[str, ...] = ("pm25", "pm10", "no2", "so2", "co", "o3")


class WaqiErrorKind(str, Enum):
    INVALID_INPUT = "invalid_input"
    AUTH_ERROR = "auth_error"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    NOT_FOUND = "not_found"
    INVALID_RESPONSE = "invalid_response"
    MISSING_FIELDS = "missing_fields"


class WaqiClientError(Exception):
    def __init__(self, kind: WaqiErrorKind, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class StationSearchResult:
    uid: int | None
    station_name: str
    aqi_raw: Any
    timestamp_str: str | None
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class AqiReading:
    query: str
    station_name: str | None
    aqi: float | int | None
    aqi_raw: Any
    dominant_pollutant: str | None
    pollutants: dict[str, float | None] = field(default_factory=dict)
    latitude: float | None = None
    longitude: float | None = None
    observation_time: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    missing_pollutants: list[str] = field(default_factory=list)


def _to_float_or_none(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        if val != val or val in (float("inf"), float("-inf")):
            return None
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned or cleaned in ("-", "N/A", "null", "None"):
            return None
        try:
            num = float(cleaned)
            if num != num or num in (float("inf"), float("-inf")):
                return None
            return num
        except ValueError:
            return None
    return None


def _parse_aqi_value(raw_aqi: Any) -> tuple[float | int | None, bool]:
    if raw_aqi is None or isinstance(raw_aqi, bool):
        return None, False
    if isinstance(raw_aqi, int):
        return raw_aqi, True
    if isinstance(raw_aqi, float):
        if raw_aqi != raw_aqi or raw_aqi in (float("inf"), float("-inf")):
            return None, False
        return (int(raw_aqi) if raw_aqi.is_integer() else raw_aqi), True
    if isinstance(raw_aqi, str):
        cleaned = raw_aqi.strip()
        if not cleaned or cleaned == "-":
            return None, False
        try:
            num = float(cleaned)
            if num != num or num in (float("inf"), float("-inf")):
                return None, False
            return (int(num) if num.is_integer() else num), True
        except ValueError:
            return None, False
    return None, False


def _extract_geo(city_obj: Any) -> tuple[float | None, float | None]:
    if not isinstance(city_obj, dict):
        return None, None
    geo = city_obj.get("geo")
    if not isinstance(geo, (list, tuple)) or len(geo) < 2:
        return None, None
    lat = _to_float_or_none(geo[0])
    lon = _to_float_or_none(geo[1])
    return lat, lon


def _extract_timestamp(time_obj: Any) -> str | None:
    if not isinstance(time_obj, dict):
        return None
    for key in ("iso", "s"):
        val = time_obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_pollutants(iaqi_obj: Any) -> tuple[dict[str, float | None], list[str]]:
    pollutants: dict[str, float | None] = {}
    missing: list[str] = []
    iaqi_dict = iaqi_obj if isinstance(iaqi_obj, dict) else {}

    for key in POLLUTANT_KEYS:
        entry = iaqi_dict.get(key)
        raw_val = entry.get("v") if isinstance(entry, dict) else entry
        parsed = _to_float_or_none(raw_val)
        pollutants[key] = parsed
        if parsed is None:
            missing.append(key)

    return pollutants, missing


class WaqiClient:
    def __init__(
        self,
        app_config: AppConfig = config,
        base_url: str = WAQI_BASE_URL,
        session: requests.Session | None = None,
    ) -> None:
        self.config = app_config
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _require_token(self) -> str:
        token = (self.config.waqi_api_token or "").strip()
        if not token or token == "your_waqi_api_token_here":
            raise WaqiClientError(
                WaqiErrorKind.AUTH_ERROR,
                "WAQI_API_TOKEN is missing or still set to the placeholder value in .env.",
            )
        return token

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(
                url,
                params=params,
                timeout=self.config.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise WaqiClientError(
                WaqiErrorKind.TIMEOUT,
                f"WAQI API request timed out after {self.config.request_timeout_seconds}s.",
            ) from exc
        except requests.ConnectionError as exc:
            raise WaqiClientError(
                WaqiErrorKind.NETWORK_ERROR,
                "Network connection failed while contacting the WAQI API.",
            ) from exc
        except requests.RequestException as exc:
            raise WaqiClientError(
                WaqiErrorKind.NETWORK_ERROR,
                f"HTTP request error while contacting WAQI API: {exc}",
            ) from exc

        code = resp.status_code
        if code in (401, 403):
            raise WaqiClientError(
                WaqiErrorKind.AUTH_ERROR,
                "WAQI API authentication failed. Check WAQI_API_TOKEN in .env.",
                status_code=code,
            )
        if code == 429:
            raise WaqiClientError(
                WaqiErrorKind.RATE_LIMIT,
                "WAQI API rate limit exceeded. Wait before sending more requests.",
                status_code=code,
            )
        if code == 404:
            raise WaqiClientError(
                WaqiErrorKind.NOT_FOUND,
                "Requested WAQI resource or city was not found.",
                status_code=code,
            )
        if code >= 500:
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                f"WAQI API server error (HTTP {code}).",
                status_code=code,
            )
        if code >= 400:
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                f"WAQI API rejected request (HTTP {code}).",
                status_code=code,
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                "WAQI API returned invalid JSON.",
                status_code=code,
            ) from exc

        if not isinstance(payload, dict):
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                "WAQI API response root must be a JSON object.",
                status_code=code,
            )

        status = payload.get("status")
        if status == "error":
            err_msg = str(payload.get("data") or "Unknown WAQI error").strip()
            lowered = err_msg.lower()
            if "invalid key" in lowered or "token" in lowered or "unauthorized" in lowered:
                raise WaqiClientError(
                    WaqiErrorKind.AUTH_ERROR,
                    f"WAQI API authentication error: {err_msg}",
                    status_code=code,
                )
            if "quota" in lowered or "rate" in lowered or "limit" in lowered:
                raise WaqiClientError(
                    WaqiErrorKind.RATE_LIMIT,
                    f"WAQI API rate limit reached: {err_msg}",
                    status_code=code,
                )
            if "unknown station" in lowered or "not found" in lowered:
                raise WaqiClientError(
                    WaqiErrorKind.NOT_FOUND,
                    f"City or station not found in WAQI: {err_msg}",
                    status_code=code,
                )
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                f"WAQI API error: {err_msg}",
                status_code=code,
            )

        if status != "ok":
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                f"Unexpected WAQI response status: {status!r}.",
                status_code=code,
            )

        return payload

    def search_cities(self, keyword: str) -> list[StationSearchResult]:
        token = self._require_token()
        cleaned = (keyword or "").strip()
        if not cleaned:
            raise WaqiClientError(
                WaqiErrorKind.INVALID_INPUT,
                "City search keyword cannot be empty.",
            )

        payload = self._request_json("/search/", params={"token": token, "keyword": cleaned})
        items = payload.get("data")
        if not isinstance(items, list):
            raise WaqiClientError(
                WaqiErrorKind.INVALID_RESPONSE,
                "WAQI search response 'data' field must be a list.",
            )

        results: list[StationSearchResult] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            station_obj = entry.get("station") if isinstance(entry.get("station"), dict) else {}
            name = station_obj.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            geo = station_obj.get("geo")
            lat = _to_float_or_none(geo[0]) if isinstance(geo, (list, tuple)) and len(geo) >= 1 else None
            lon = _to_float_or_none(geo[1]) if isinstance(geo, (list, tuple)) and len(geo) >= 2 else None
            time_obj = entry.get("time") if isinstance(entry.get("time"), dict) else {}
            ts = time_obj.get("stime") if isinstance(time_obj.get("stime"), str) else None
            uid_raw = entry.get("uid")
            uid = int(uid_raw) if isinstance(uid_raw, int) and not isinstance(uid_raw, bool) else None

            results.append(
                StationSearchResult(
                    uid=uid,
                    station_name=name.strip(),
                    aqi_raw=entry.get("aqi"),
                    timestamp_str=ts,
                    latitude=lat,
                    longitude=lon,
                )
            )

        if not results:
            raise WaqiClientError(
                WaqiErrorKind.NOT_FOUND,
                f"No monitoring stations matched '{cleaned}'.",
            )
        return results

    def get_city_aqi(self, city_or_feed_id: str) -> AqiReading:
        token = self._require_token()
        cleaned = (city_or_feed_id or "").strip()
        if not cleaned:
            raise WaqiClientError(
                WaqiErrorKind.INVALID_INPUT,
                "City name or station feed identifier cannot be empty.",
            )

        encoded_target = requests.utils.quote(cleaned, safe="@:;")
        try:
            payload = self._request_json(f"/feed/{encoded_target}/", params={"token": token})
        except WaqiClientError as exc:
            if (
                exc.kind == WaqiErrorKind.NOT_FOUND
                and not cleaned.startswith(("@", "geo:"))
            ):
                matches = self.search_cities(cleaned)
                first_with_uid = next((m for m in matches if m.uid is not None), None)
                if first_with_uid is None:
                    raise
                payload = self._request_json(
                    f"/feed/@{first_with_uid.uid}/",
                    params={"token": token},
                )
            else:
                raise

        data = payload.get("data")
        if not isinstance(data, dict):
            raise WaqiClientError(
                WaqiErrorKind.MISSING_FIELDS,
                "WAQI feed response is missing a valid 'data' object.",
            )

        missing_fields: list[str] = []

        raw_aqi = data.get("aqi")
        aqi_val, aqi_ok = _parse_aqi_value(raw_aqi)
        if not aqi_ok:
            missing_fields.append("aqi")

        city_obj = data.get("city")
        station_name: str | None = None
        if isinstance(city_obj, dict) and isinstance(city_obj.get("name"), str) and city_obj["name"].strip():
            station_name = city_obj["name"].strip()
        else:
            missing_fields.append("city.name")

        lat, lon = _extract_geo(city_obj)
        if lat is None:
            missing_fields.append("city.geo.lat")
        if lon is None:
            missing_fields.append("city.geo.lon")

        obs_time = _extract_timestamp(data.get("time"))
        if obs_time is None:
            missing_fields.append("time")

        dom_pol_raw = data.get("dominentpol")
        dominant_pollutant = (
            dom_pol_raw.strip() if isinstance(dom_pol_raw, str) and dom_pol_raw.strip() else None
        )

        pollutants, missing_pollutants = _extract_pollutants(data.get("iaqi"))

        if aqi_val is None and station_name is None:
            raise WaqiClientError(
                WaqiErrorKind.MISSING_FIELDS,
                f"WAQI response for '{cleaned}' lacks both AQI and station name.",
            )

        return AqiReading(
            query=cleaned,
            station_name=station_name,
            aqi=aqi_val,
            aqi_raw=raw_aqi,
            dominant_pollutant=dominant_pollutant,
            pollutants=pollutants,
            latitude=lat,
            longitude=lon,
            observation_time=obs_time,
            missing_fields=missing_fields,
            missing_pollutants=missing_pollutants,
        )