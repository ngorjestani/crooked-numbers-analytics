"""Environment-backed application settings."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

_AZURE_CONTAINER_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")
_AZURE_ACCOUNT_PATTERN = re.compile(r"^[a-z0-9]{3,24}$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"
_DEFAULT_DATA_ROOT = REPOSITORY_ROOT / "data"


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration needed to access analytical datasets."""

    azure_storage_account_url: str | None
    azure_storage_container: str = "baseball-data"
    analytics_data_root: Path = _DEFAULT_DATA_ROOT

    def __post_init__(self) -> None:
        if not _AZURE_CONTAINER_PATTERN.fullmatch(self.azure_storage_container):
            raise ValueError("AZURE_STORAGE_CONTAINER is not a valid container name")

        if self.azure_storage_account_url is not None:
            _account_name_from_url(self.azure_storage_account_url)

    @classmethod
    def from_env(cls, env_file: str | Path | None = _DEFAULT_ENV_FILE) -> Settings:
        """Load settings from an optional dotenv file and the environment."""

        if env_file is not None:
            load_dotenv(dotenv_path=Path(env_file), override=False)

        account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "").strip() or None
        container = os.getenv("AZURE_STORAGE_CONTAINER", "baseball-data").strip()
        data_root = _resolve_data_root(os.getenv("ANALYTICS_DATA_ROOT", "./data"))
        return cls(
            azure_storage_account_url=account_url,
            azure_storage_container=container,
            analytics_data_root=data_root,
        )

    @property
    def azure_storage_account_name(self) -> str:
        """Return the storage account name parsed from its Blob service URL."""

        if self.azure_storage_account_url is None:
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL is not configured")
        return _account_name_from_url(self.azure_storage_account_url)


def get_settings(env_file: str | Path | None = _DEFAULT_ENV_FILE) -> Settings:
    """Load settings and require the Azure storage configuration."""

    settings = Settings.from_env(env_file)
    if settings.azure_storage_account_url is None:
        raise ValueError("AZURE_STORAGE_ACCOUNT_URL is not configured")
    return settings


def _account_name_from_url(account_url: str) -> str:
    parsed = urlparse(account_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("AZURE_STORAGE_ACCOUNT_URL must be a valid HTTPS URL")

    account_name = parsed.hostname.split(".", maxsplit=1)[0]
    if not _AZURE_ACCOUNT_PATTERN.fullmatch(account_name):
        raise ValueError("AZURE_STORAGE_ACCOUNT_URL has an invalid account name")
    return account_name


def _resolve_data_root(data_root: str | Path) -> Path:
    path = Path(data_root).expanduser()
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    return path.resolve()
