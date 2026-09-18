from pathlib import Path

import pytest

from crooked_numbers_analytics import settings as settings_module
from crooked_numbers_analytics.settings import Settings, get_settings


def test_settings_loads_repository_env_independently_of_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)

    def load_repository_env(dotenv_path: Path, override: bool) -> None:
        repository_env = (
            Path(settings_module.__file__).resolve().parents[2] / ".env"
        )
        assert dotenv_path == repository_env
        assert override is False
        monkeypatch.setenv(
            "AZURE_STORAGE_ACCOUNT_URL",
            "https://crookednumbers.blob.core.windows.net",
        )

    monkeypatch.setattr(settings_module, "load_dotenv", load_repository_env)

    settings = get_settings()

    assert settings.azure_storage_account_name == "crookednumbers"


def test_get_settings_loads_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AZURE_STORAGE_ACCOUNT_URL=https://crookednumbers.blob.core.windows.net\n"
        "AZURE_STORAGE_CONTAINER=research-data\n"
    )

    settings = get_settings(env_file)

    assert settings.azure_storage_account_url == (
        "https://crookednumbers.blob.core.windows.net"
    )
    assert settings.azure_storage_account_name == "crookednumbers"
    assert settings.azure_storage_container == "research-data"


def test_environment_variables_take_precedence_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AZURE_STORAGE_ACCOUNT_URL=https://dotenvaccount.blob.core.windows.net\n"
        "AZURE_STORAGE_CONTAINER=dotenv-data\n"
    )
    monkeypatch.setenv(
        "AZURE_STORAGE_ACCOUNT_URL",
        "https://environmentaccount.blob.core.windows.net",
    )
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "environment-data")

    settings = get_settings(env_file)

    assert settings.azure_storage_account_name == "environmentaccount"
    assert settings.azure_storage_container == "environment-data"


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


def test_get_settings_requires_azure_account_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)

    with pytest.raises(ValueError, match="AZURE_STORAGE_ACCOUNT_URL is not configured"):
        get_settings(env_file=None)
