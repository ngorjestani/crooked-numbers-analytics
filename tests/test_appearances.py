from pathlib import Path

import duckdb
import pytest

from crooked_numbers_analytics import appearances


@pytest.fixture
def statcast_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE synthetic_statcast (
            game_pk BIGINT,
            game_date DATE,
            season BIGINT,
            game_type VARCHAR,
            home_team VARCHAR,
            away_team VARCHAR,
            inning BIGINT,
            inning_topbot VARCHAR,
            at_bat_number BIGINT,
            pitch_number BIGINT,
            pitcher BIGINT,
            player_name VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO synthetic_statcast VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # Away batters: the home team pitches. Pitcher 101 starts, then 102.
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                1, "Top", 1, 1, 101, "Starter, Home",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                1, "Top", 1, 2, 101, "Starter, Home",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                1, "Top", 2, 1, 102, "Reliever, Early",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                2, "Top", 5, 1, 103, "Reliever, Late",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                2, "Top", 5, 2, 103, "Reliever, Late",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                2, "Top", 5, 3, 103, "Reliever, Late",
            ),
            # Home batters: the away team pitches.
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                1, "Bot", 3, 1, 201, "Starter, Away",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                1, "Bot", 3, 2, 201, "Starter, Away",
            ),
            (
                1, "2024-06-01", 2024, "R", "MIL", "CHC",
                3, "Bot", 8, 1, 202, "Reliever, Away",
            ),
            # Same pitcher ID in another game is a separate appearance.
            (
                2, "2024-06-02", 2024, "R", "CHC", "MIL",
                1, "Bot", 2, 1, 101, "Starter, Home",
            ),
            # Excluded by the regular-season default.
            (
                3, "2024-10-01", 2024, "P", "MIL", "CHC",
                1, "Top", 1, 1, 301, "Postseason, Pitcher",
            ),
        ],
    )

    parquet_path = tmp_path / "statcast.parquet"
    con.execute(f"COPY synthetic_statcast TO '{parquet_path}' (FORMAT PARQUET)")
    monkeypatch.setattr(appearances, "dataset_path", lambda _path: str(parquet_path))

    yield con
    con.close()


def test_builds_starter_and_reliever_appearances(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    rows = statcast_connection.sql(
        """
        SELECT pitcher_id, is_start, pitch_count, first_inning, last_inning
        FROM pitcher_appearances
        WHERE game_pk = 1 AND pitching_team = 'MIL'
        ORDER BY pitcher_id
        """
    ).fetchall()

    assert rows == [
        (101, True, 2, 1, 1),
        (102, False, 1, 1, 1),
        (103, False, 3, 2, 2),
    ]


def test_derives_both_pitching_teams_and_one_starter_each(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    rows = statcast_connection.sql(
        """
        SELECT pitching_team, count(*) FILTER (WHERE is_start) AS starters
        FROM pitcher_appearances
        WHERE game_pk = 1
        GROUP BY pitching_team
        ORDER BY pitching_team
        """
    ).fetchall()

    assert rows == [("CHC", 1), ("MIL", 1)]


def test_uses_game_team_and_pitcher_grain_and_preserves_pitcher_id(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    rows = statcast_connection.sql(
        """
        SELECT game_pk, pitching_team, pitcher_id, pitcher_name
        FROM pitcher_appearances
        WHERE pitcher_id = 101
        ORDER BY game_pk
        """
    ).fetchall()

    assert rows == [
        (1, "MIL", 101, "Starter, Home"),
        (2, "MIL", 101, "Starter, Home"),
    ]
    assert statcast_connection.sql(
        """
        SELECT count(*) = count(DISTINCT (game_pk, pitching_team, pitcher_id))
        FROM pitcher_appearances
        """
    ).fetchone() == (True,)


def test_includes_only_regular_season_by_default(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    assert statcast_connection.sql(
        "SELECT DISTINCT game_pk FROM pitcher_appearances ORDER BY game_pk"
    ).fetchall() == [(1,), (2,)]


def test_can_select_another_game_type(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(
        statcast_connection, game_type="P"
    )

    assert statcast_connection.sql(
        "SELECT game_pk, pitcher_id FROM pitcher_appearances"
    ).fetchall() == [(3, 301)]


def test_explicit_seasons_build_narrow_partition_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_paths: list[str] = []

    def record_path(path: str) -> str:
        requested_paths.append(path)
        return path

    monkeypatch.setattr(appearances, "dataset_path", record_path)

    assert appearances._statcast_paths([2024, 2023, 2024]) == [
        "raw/statcast/season=2023/game_date=*/statcast.parquet",
        "raw/statcast/season=2024/game_date=*/statcast.parquet",
    ]
    assert requested_paths == [
        "raw/statcast/season=2023/game_date=*/statcast.parquet",
        "raw/statcast/season=2024/game_date=*/statcast.parquet",
    ]


def test_rejects_unexpected_inning_half(
    statcast_connection: duckdb.DuckDBPyConnection,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statcast_connection.execute(
        """
        INSERT INTO synthetic_statcast VALUES
            (4, DATE '2024-06-03', 2024, 'R', 'MIL', 'CHC', 1, 'Middle',
             1, 1, 401, 'Unexpected, Pitcher')
        """
    )

    parquet_path = tmp_path / "unexpected.parquet"
    statcast_connection.execute(
        f"COPY synthetic_statcast TO '{parquet_path}' (FORMAT PARQUET)"
    )
    monkeypatch.setattr(appearances, "dataset_path", lambda _path: str(parquet_path))
    appearances.create_pitcher_appearances_view(statcast_connection)

    with pytest.raises(duckdb.InvalidInputException):
        statcast_connection.sql("SELECT * FROM pitcher_appearances").fetchall()
