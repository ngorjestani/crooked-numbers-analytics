"""DuckDB helpers for directly querying Azure-hosted Parquet data."""

from __future__ import annotations

import duckdb

from crooked_numbers_analytics.settings import Settings


def azure_dataset_path(relative_path: str, container: str = "baseball-data") -> str:
    """Build an ``az://`` URI for a path or glob inside an Azure container."""

    clean_container = container.strip("/")
    clean_path = relative_path.strip("/")
    if not clean_container:
        raise ValueError("container must not be empty")
    if not clean_path:
        raise ValueError("relative_path must not be empty")
    return f"az://{clean_container}/{clean_path}"


def open_database(settings: Settings | None = None) -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection configured for Azure when requested."""

    connection = duckdb.connect(":memory:")
    if settings is None or settings.azure_storage_account_url is None:
        return connection

    try:
        connection.install_extension("azure")
        connection.load_extension("azure")
        account_name = settings.azure_storage_account_name
        connection.execute(
            f"""
            CREATE OR REPLACE SECRET azure_blob (
                TYPE azure,
                PROVIDER credential_chain,
                ACCOUNT_NAME '{account_name}'
            )
            """
        )
    except Exception:
        connection.close()
        raise

    return connection
