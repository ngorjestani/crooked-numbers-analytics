from unittest.mock import MagicMock

import pytest

from crooked_numbers_analytics import db
from crooked_numbers_analytics.settings import Settings


def test_open_database_configures_in_memory_azure_connection(
    monkeypatch,
) -> None:
    connection = MagicMock()
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(db.duckdb, "connect", connect)
    settings = Settings(
        azure_storage_account_url="https://crookednumbers.blob.core.windows.net"
    )

    result = db.open_database(settings)

    assert result is connection
    connect.assert_called_once_with(":memory:")
    connection.install_extension.assert_called_once_with("azure")
    connection.load_extension.assert_called_once_with("azure")
    assert "PROVIDER credential_chain" in connection.execute.call_args.args[0]
    assert "ACCOUNT_NAME 'crookednumbers'" in connection.execute.call_args.args[0]


def test_open_database_loads_settings_when_not_supplied(monkeypatch) -> None:
    settings = Settings(
        azure_storage_account_url="https://crookednumbers.blob.core.windows.net"
    )
    monkeypatch.setattr(db, "get_settings", MagicMock(return_value=settings))
    monkeypatch.setattr(db.duckdb, "connect", MagicMock(return_value=MagicMock()))

    db.open_database()

    db.get_settings.assert_called_once_with()


def test_open_database_validates_azure_settings_before_connecting(monkeypatch) -> None:
    connect = MagicMock()
    monkeypatch.setattr(db.duckdb, "connect", connect)

    with pytest.raises(ValueError, match="AZURE_STORAGE_ACCOUNT_URL is not configured"):
        db.open_database(Settings(azure_storage_account_url=None))

    connect.assert_not_called()
