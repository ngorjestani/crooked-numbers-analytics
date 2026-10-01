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
            player_name VARCHAR,
            events VARCHAR,
            description VARCHAR,
            pitch_type VARCHAR,
            release_speed DOUBLE,
            launch_speed DOUBLE,
            launch_speed_angle BIGINT,
            outs_when_up BIGINT,
            post_home_score BIGINT,
            post_away_score BIGINT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO synthetic_statcast (
            game_pk, game_date, season, game_type, home_team, away_team,
            inning, inning_topbot, at_bat_number, pitch_number,
            pitcher, player_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
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
                4, "Top", 5, 3, 103, "Reliever, Late",
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
    con.executemany(
        """
        INSERT INTO synthetic_statcast (
            game_pk, game_date, season, game_type, home_team, away_team,
            inning, inning_topbot, at_bat_number, pitch_number,
            pitcher, player_name, events, description, pitch_type,
            release_speed, launch_speed, launch_speed_angle
        )
        VALUES (
            4, DATE '2024-06-03', 2024, 'R', 'MIL', 'CHC',
            ?, 'Top', ?, ?, 401, 'Metrics, Pitcher', ?, ?, ?, ?, ?, ?
        )
        """,
        [
            # Strikeout: called strike, foul, swinging strike.
            (7, 1, 1, None, "called_strike", "FF", 95.0, None, None),
            (7, 1, 2, None, "foul", "SL", 86.0, None, None),
            (7, 1, 3, "strikeout", "swinging_strike", "FF", 97.0, None, None),
            # Four-pitch walk.
            (7, 2, 1, None, "ball", "FF", 94.0, None, None),
            (7, 2, 2, None, "ball", "CH", 87.0, None, None),
            (7, 2, 3, None, "ball", "SL", 85.0, None, None),
            (7, 2, 4, "walk", "ball", "CU", 80.0, None, None),
            # Five balls in play; two lack tracking measurements.
            (8, 3, 1, "home_run", "hit_into_play", "FF", 96.0, 100.0, 6),
            (8, 4, 1, "double", "hit_into_play", "CH", 86.0, 94.9, 4),
            (8, 5, 1, "field_out", "hit_into_play", "SI", 93.0, 95.0, 2),
            (8, 6, 1, "field_out", "hit_into_play", "SI", 92.0, None, None),
            (8, 7, 1, "field_out", "hit_into_play", "SI", 91.0, None, None),
        ],
    )
    con.executemany(
        """
        INSERT INTO synthetic_statcast (
            game_pk, game_date, season, game_type, home_team, away_team,
            inning, inning_topbot, at_bat_number, pitch_number,
            pitcher, player_name, events, description, pitch_type,
            release_speed, outs_when_up
        ) VALUES (
            5, DATE '2024-06-04', 2024, 'R', 'MIL', 'CHC',
            ?, ?, ?, ?, ?, ?, ?, ?, 'CH', 85.0, ?
        )
        """,
        [
            # A runner out between pitches changes outs_when_up without an event.
            (7, "Top", 1, 1, 501, "Runner Outs, Pitcher", None, "ball", 0),
            (7, "Top", 1, 2, 501, "Runner Outs, Pitcher", None, "ball", 1),
            (
                7,
                "Top",
                1,
                3,
                501,
                "Runner Outs, Pitcher",
                "double_play",
                "hit_into_play",
                1,
            ),
            # A later half-inning proves that the top half completed three outs.
            (
                7,
                "Bot",
                2,
                1,
                601,
                "Other, Pitcher",
                "field_out",
                "hit_into_play",
                2,
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
        SELECT
            pitcher_id, is_start, pitch_count, first_inning, last_inning,
            innings_appeared, ups
        FROM pitcher_appearances
        WHERE game_pk = 1 AND pitching_team = 'MIL'
        ORDER BY pitcher_id
        """
    ).fetchall()

    assert rows == [
        (101, True, 2, 1, 1, 1, 1),
        (102, False, 1, 1, 1, 1, 1),
        (103, False, 3, 2, 4, 2, 2),
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


def test_derives_appearance_results_and_pitch_process_metrics(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    row = statcast_connection.sql(
        """
        SELECT
            pitch_count, innings_appeared, ups, outs_recorded, innings_pitched,
            batters_faced, strikeouts, walks, hits, home_runs,
            strikes, strike_rate, swings, whiffs, whiff_rate,
            called_strikes, csw, csw_rate
        FROM pitcher_appearances
        WHERE game_pk = 4 AND pitcher_id = 401
        """
    ).fetchone()

    assert row[:10] == (12, 2, 2, 4, 4 / 3, 7, 1, 1, 2, 1)
    assert row[10:] == pytest.approx((8, 8 / 12, 7, 1, 1 / 7, 1, 2, 2 / 12))


def test_derives_velocity_and_measured_contact_quality(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    row = statcast_connection.sql(
        """
        SELECT
            fastball_pitches, avg_fastball_velocity, max_fastball_velocity,
            balls_in_play, exit_velocity_balls,
            avg_exit_velocity, max_exit_velocity,
            hard_hit_count, hard_hit_rate,
            barrel_eligible_balls, barrel_count, barrel_rate
        FROM pitcher_appearances
        WHERE game_pk = 4 AND pitcher_id = 401
        """
    ).fetchone()

    assert row[:5] == (4, 95.5, 97.0, 5, 3)
    assert row[5:] == pytest.approx(
        ((100.0 + 94.9 + 95.0) / 3, 100.0, 2, 2 / 3, 3, 1, 1 / 3)
    )


def test_outs_include_non_terminal_runner_outs(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    assert statcast_connection.sql(
        """
        SELECT outs_recorded, innings_pitched
        FROM pitcher_appearances
        WHERE game_pk = 5 AND pitcher_id = 501
        """
    ).fetchone() == (3, 1.0)


def test_zero_denominators_and_no_fastballs_return_null_rates_and_velocity(
    statcast_connection: duckdb.DuckDBPyConnection,
) -> None:
    appearances.create_pitcher_appearances_view(statcast_connection)

    row = statcast_connection.sql(
        """
        SELECT
            fastball_pitches, avg_fastball_velocity, max_fastball_velocity,
            swings, whiff_rate, exit_velocity_balls, hard_hit_rate,
            barrel_eligible_balls, barrel_rate
        FROM pitcher_appearances
        WHERE game_pk = 1 AND pitcher_id = 102
        """
    ).fetchone()

    assert row == (0, None, None, 0, None, 0, None, 0, None)


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
    ).fetchall() == [(1,), (2,), (4,), (5,)]


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
        INSERT INTO synthetic_statcast (
            game_pk, game_date, season, game_type, home_team, away_team,
            inning, inning_topbot, at_bat_number, pitch_number,
            pitcher, player_name
        ) VALUES
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
