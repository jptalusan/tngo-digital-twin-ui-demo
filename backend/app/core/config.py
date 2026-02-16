from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

_backend_env = Path(__file__).resolve().parents[2] / ".env"
_root_env = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_root_env)
load_dotenv(_backend_env)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/tngo"
    )
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    cors_origins: list[str] = None  # type: ignore[assignment]
    default_max_wait_minutes: int = int(os.getenv("DEFAULT_MAX_WAIT_MINUTES", "20"))
    default_max_invehicle_minutes: int = int(
        os.getenv("DEFAULT_MAX_INVEHICLE_MINUTES", "60")
    )
    default_max_total_minutes: int = int(os.getenv("DEFAULT_MAX_TOTAL_MINUTES", "90"))
    default_walk_speed_mps: float = float(os.getenv("DEFAULT_WALK_SPEED_MPS", "1.4"))
    default_transfer_limit: int = int(os.getenv("DEFAULT_TRANSFER_LIMIT", "1"))
    score_weight_total_minutes: float = float(
        os.getenv("SCORE_WEIGHT_TOTAL_MINUTES", "1.0")
    )
    score_weight_wait_minutes: float = float(
        os.getenv("SCORE_WEIGHT_WAIT_MINUTES", "0.5")
    )
    score_weight_walk_meters: float = float(
        os.getenv("SCORE_WEIGHT_WALK_METERS", "0.001")
    )
    default_min_transfer_minutes: int = int(
        os.getenv("DEFAULT_MIN_TRANSFER_MINUTES", "3")
    )
    boc_hub_search_m: int = int(os.getenv("BOC_HUB_SEARCH_M", "8000"))
    transfer_walk_radius_m: int = int(os.getenv("TRANSFER_WALK_RADIUS_M", "300"))
    enable_osrm: bool = os.getenv("ENABLE_OSRM", "false").lower() == "true"
    osrm_url: str = os.getenv("OSRM_URL", "http://localhost:5000")
    database_url_test: str = os.getenv(
        "DATABASE_URL_TEST",
        "postgresql+psycopg://postgres:postgres@localhost:5432/tngo_test",
    )
    default_on_demand_speed_kmph: float = float(
        os.getenv("DEFAULT_ONDEMAND_SPEED_KMPH", "30")
    )
    default_brt_speed_kmph: float = float(os.getenv("DEFAULT_BRT_SPEED_KMPH", "45"))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "cors_origins", _split_csv(os.getenv("CORS_ORIGINS", ""))
        )


settings = Settings()
