import pytest

from crooked_numbers_analytics.db import azure_dataset_path, open_database


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


def test_open_database_is_in_memory() -> None:
    with open_database() as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)
