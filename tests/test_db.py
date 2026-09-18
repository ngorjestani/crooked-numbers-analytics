from unittest.mock import MagicMock

from crooked_numbers_analytics import db


def test_open_database_returns_in_memory_connection(monkeypatch) -> None:
    connection = MagicMock()
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(db.duckdb, "connect", connect)

    result = db.open_database()

    assert result is connection
    connect.assert_called_once_with(":memory:")
    connection.install_extension.assert_not_called()
    connection.load_extension.assert_not_called()
