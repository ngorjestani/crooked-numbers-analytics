"""DuckDB helpers for querying local analytical datasets."""

from __future__ import annotations

import duckdb


def open_database() -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection for local research."""

    return duckdb.connect(":memory:")
