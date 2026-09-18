"""Paths for analytical datasets."""


def azure_dataset_path(relative_path: str, container: str = "baseball-data") -> str:
    """Build an ``az://`` URI for a path or glob inside an Azure container."""

    clean_container = container.strip("/")
    clean_path = relative_path.strip("/")
    if not clean_container:
        raise ValueError("container must not be empty")
    if not clean_path:
        raise ValueError("relative_path must not be empty")
    return f"az://{clean_container}/{clean_path}"
