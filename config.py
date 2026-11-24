from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_env: str
    waqi_api_token: str
    request_timeout_seconds: int
    default_location: str
    base_dir: Path
    data_dir: Path
    assets_dir: Path
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    @property
    def has_api_token(self) -> bool:
        return bool(self.waqi_api_token and self.waqi_api_token != "your_waqi_api_token_here")

    @property
    def has_groq_api_key(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key != "your_groq_api_key_here")


def load_config() -> AppConfig:
    return AppConfig(
        app_name=os.getenv(
            "APP_NAME",
            "AI-Based Environmental Health Advisory and Intelligent Air Quality Monitoring System",
        ),
        app_env=os.getenv("APP_ENV", "development"),
        waqi_api_token=os.getenv("WAQI_API_TOKEN", "").strip(),
        request_timeout_seconds=_parse_int(os.getenv("REQUEST_TIMEOUT_SECONDS"), 10),
        default_location=os.getenv("DEFAULT_LOCATION", "Delhi").strip() or "Delhi",
        base_dir=BASE_DIR,
        data_dir=BASE_DIR / "data",
        assets_dir=BASE_DIR / "assets",
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile",
    )


config = load_config()