from pathlib import Path

import pytest

from crooked_numbers_analytics.paths import local_path_for_statcast_blob


def test_local_path_for_blob_preserves_statcast_partition_structure(
    tmp_path: Path,
) -> None:
    blob_name = (
        "raw/statcast/season=2024/game_date=2024-09-17/statcast.parquet"
    )

    assert local_path_for_statcast_blob(blob_name, tmp_path) == (
        tmp_path
        / "raw/statcast/season=2024/game_date=2024-09-17/statcast.parquet"
    )


@pytest.mark.parametrize(
    "blob_name",
    ["curated/statcast.parquet", "raw/statcast/../../outside.parquet"],
)
def test_local_path_for_blob_rejects_names_outside_statcast(
    tmp_path: Path,
    blob_name: str,
) -> None:
    with pytest.raises(ValueError):
        local_path_for_statcast_blob(blob_name, tmp_path)
