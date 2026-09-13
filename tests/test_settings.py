from pathlib import Path

import pytest

from crooked_numbers_analytics.settings import Settings


def test_settings_loads_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AZURE_STORAGE_ACCOUNT_URL=https://crookednumbers.blob.core.windows.net\n"
        "AZURE_STORAGE_CONTAINER=research-data\n"
    )

    settings = Settings.from_env(env_file)

    assert settings.azure_storage_account_url == (
        "https://crookednumbers.blob.core.windows.net"
    )
    assert settings.azure_storage_account_name == "crookednumbers"
    assert settings.azure_storage_container == "research-data"


def test_settings_uses_defaults_without_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)

    settings = Settings.from_env(env_file=None)

    assert settings.azure_storage_account_url is None
    assert settings.azure_storage_container == "baseball-data"


def test_settings_rejects_invalid_account_url() -> None:
    with pytest.raises(ValueError, match="valid HTTPS URL"):
        Settings(azure_storage_account_url="not-a-url")
