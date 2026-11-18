import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GENRES = [
    "Action",
    "Adventure",
    "Strategy",
    "RPG",
    "Indie",
    "Simulation",
    "Casual",
    "Sports",
    "Racing",
    "Free To Play",
]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    pg_host: str = os.getenv("PG_HOST", "localhost")
    pg_port: int = int(os.getenv("PG_PORT", "5433"))
    pg_db: str = os.getenv("PG_DB", "steam_dwh")
    pg_user: str = os.getenv("PG_USER", "steam")
    pg_password: str = os.getenv("PG_PASSWORD", "steam")
    genres: list[str] = field(default_factory=lambda: list(DEFAULT_GENRES))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def clean_dir(self) -> Path:
        return self.data_dir / "clean"

    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={self.pg_user} password={self.pg_password}"
        )
