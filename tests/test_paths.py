from pathlib import Path

import pytest

from crooked_numbers_analytics import settings as settings_module
from crooked_numbers_analytics.paths import azure_dataset_path, dataset_path


def test_dataset_path_uses_default_repository_data_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANALYTICS_DATA_ROOT", raising=False)

    result = dataset_path("raw/statcast/season=*/game_date=*/statcast.parquet")

    assert result == str(
        settings_module.REPOSITORY_ROOT
        / "data/raw/statcast/season=*/game_date=*/statcast.parquet"
    )


def test_dataset_path_resolves_configured_relative_root_from_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYTICS_DATA_ROOT", "./research-data")

    result = dataset_path("raw/statcast/file.parquet")

    assert result == str(
        settings_module.REPOSITORY_ROOT
        / "research-data/raw/statcast/file.parquet"
    )


def test_dataset_path_accepts_explicit_absolute_data_root(tmp_path: Path) -> None:
    assert dataset_path("raw/statcast/file.parquet", tmp_path) == str(
        tmp_path / "raw/statcast/file.parquet"
    )


def test_dataset_path_rejects_paths_outside_data_root() -> None:
    with pytest.raises(ValueError, match="inside the data root"):
        dataset_path("../secrets", "/tmp/data")
    with pytest.raises(ValueError, match="inside the data root"):
        dataset_path("/tmp/secrets", "/tmp/data")


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    [
        (
            "raw/statcast/**/*.parquet",
            "az://baseball-data/raw/statcast/**/*.parquet",
        ),
        (
            "/curated/pitcher_appearances/**/*.parquet/",
            "az://baseball-data/curated/pitcher_appearances/**/*.parquet",
        ),
    ],
)
def test_azure_dataset_path(relative_path: str, expected: str) -> None:
    assert azure_dataset_path(relative_path) == expected


def test_azure_dataset_path_supports_another_container() -> None:
    assert azure_dataset_path("sample.parquet", "research") == (
        "az://research/sample.parquet"
    )


def test_azure_dataset_path_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="container"):
        azure_dataset_path("data.parquet", "")
    with pytest.raises(ValueError, match="relative_path"):
        azure_dataset_path("")
