"""Paths for analytical datasets."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from crooked_numbers_analytics.settings import Settings, _resolve_data_root

STATCAST_PREFIX = "raw/statcast"


def dataset_path(
    relative_path: str,
    data_root: str | Path | None = None,
) -> str:
    """Build an absolute path inside the configured local data directory."""

    clean_path = _clean_relative_path(relative_path)
    root = (
        Settings.from_env().analytics_data_root
        if data_root is None
        else _resolve_data_root(data_root)
    )
    return str(root.joinpath(*clean_path.parts))


def azure_dataset_path(relative_path: str, container: str = "baseball-data") -> str:
    """Build an ``az://`` URI for a path or glob inside an Azure container."""

    clean_container = container.strip("/")
    clean_path = relative_path.strip("/")
    if not clean_container:
        raise ValueError("container must not be empty")
    if not clean_path:
        raise ValueError("relative_path must not be empty")
    return f"az://{clean_container}/{clean_path}"


def local_path_for_statcast_blob(blob_name: str, data_root: str | Path) -> Path:
    """Map a Statcast blob name to its matching path below the data root."""

    blob_path = _clean_relative_path(blob_name)
    if blob_path.parts[:2] != ("raw", "statcast"):
        raise ValueError(f"blob is outside {STATCAST_PREFIX}: {blob_name}")
    return _resolve_data_root(data_root).joinpath(*blob_path.parts)


def _clean_relative_path(relative_path: str) -> PurePosixPath:
    if PurePosixPath(relative_path).is_absolute():
        raise ValueError("relative_path must stay inside the data root")
    value = relative_path.strip().strip("/")
    path = PurePosixPath(value)
    if not value:
        raise ValueError("relative_path must not be empty")
    if ".." in path.parts:
        raise ValueError("relative_path must stay inside the data root")
    return path
