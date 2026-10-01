from datetime import date

import duckdb
import pytest

from crooked_numbers_analytics.workload import create_pitcher_workload_view


@pytest.fixture
def workload_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE pitcher_appearances (
            game_pk BIGINT,
            game_date DATE,
            season BIGINT,
            pitching_team VARCHAR,
            pitcher_id BIGINT,
            pitcher_name VARCHAR,
            is_start BOOLEAN,
            pitch_count BIGINT,
            first_inning BIGINT,
            last_inning BIGINT,
            innings_appeared BIGINT,
            ups BIGINT,
            outs_recorded BIGINT,
            innings_pitched DOUBLE
        )
        """
    )
    con.executemany(
        """
        INSERT INTO pitcher_appearances
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 7, 6 + ?, ?, ?, ?, ?)
        """,
        [
            (
                101,
                "2024-06-08",
                2024,
                "MIL",
                10,
                "Workload, Pitcher",
                False,
                15,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                102,
                "2024-06-09",
                2024,
                "MIL",
                10,
                "Workload, Pitcher",
                False,
                20,
                2,
                2,
                2,
                4,
                4 / 3,
            ),
            # The June 10 team change must not reset pitcher 10's workload.
            (
                103,
                "2024-06-10",
                2024,
                "CHC",
                10,
                "Workload, Pitcher",
                True,
                10,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                104,
                "2024-06-11",
                2024,
                "CHC",
                10,
                "Workload, Pitcher",
                False,
                12,
                1,
                1,
                1,
                3,
                1.0,
            ),
            # A new season resets cumulative, but not identity, partitions.
            (
                105,
                "2025-04-01",
                2025,
                "CHC",
                10,
                "Workload, Pitcher",
                False,
                8,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                201,
                "2024-06-08",
                2024,
                "MIL",
                20,
                "Rested, Pitcher",
                False,
                12,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                202,
                "2024-06-10",
                2024,
                "MIL",
                20,
                "Rested, Pitcher",
                False,
                9,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                203,
                "2024-06-15",
                2024,
                "MIL",
                20,
                "Rested, Pitcher",
                False,
                8,
                1,
                1,
                1,
                3,
                1.0,
            ),
            # Two June 9 games exercise calendar-day aggregation.
            (
                301,
                "2024-06-08",
                2024,
                "MIL",
                30,
                "Doubleheader, Pitcher",
                False,
                5,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                302,
                "2024-06-09",
                2024,
                "MIL",
                30,
                "Doubleheader, Pitcher",
                False,
                7,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                303,
                "2024-06-09",
                2024,
                "MIL",
                30,
                "Doubleheader, Pitcher",
                False,
                8,
                1,
                1,
                1,
                3,
                1.0,
            ),
            (
                304,
                "2024-06-10",
                2024,
                "MIL",
                30,
                "Doubleheader, Pitcher",
                False,
                6,
                1,
                1,
                1,
                3,
                1.0,
            ),
        ],
    )
    create_pitcher_workload_view(con)

    yield con
    con.close()


def test_back_to_back_workload_excludes_current_appearance(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    row = workload_connection.sql(
        """
        SELECT
            previous_appearance_date,
            days_rest,
            pitches_previous_day,
            pitches_last_2_days,
            ups_previous_day,
            ups_last_2_days,
            appearances_previous_day,
            appearances_last_2_days,
            pitched_previous_day,
            pitched_two_consecutive_days,
            pitching_team,
            is_start
        FROM pitcher_workload
        WHERE pitcher_id = 10 AND game_date = DATE '2024-06-10'
        """
    ).fetchone()

    assert row == (
        date(2024, 6, 9),
        0,
        20,
        35,
        2,
        3,
        1,
        2,
        True,
        True,
        "CHC",
        True,
    )


def test_day_off_and_longer_rest(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    rows = workload_connection.sql(
        """
        SELECT
            game_date,
            previous_appearance_date,
            days_rest,
            pitches_previous_day,
            pitches_last_3_days,
            pitches_last_7_days,
            pitched_previous_day
        FROM pitcher_workload
        WHERE pitcher_id = 20 AND game_date > DATE '2024-06-08'
        ORDER BY game_date
        """
    ).fetchall()

    assert rows == [
        (date(2024, 6, 10), date(2024, 6, 8), 1, 0, 12, 12, False),
        (date(2024, 6, 15), date(2024, 6, 10), 4, 0, 0, 21, False),
    ]


def test_first_known_appearance_has_null_rest_and_zero_history(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    row = workload_connection.sql(
        """
        SELECT
            previous_appearance_date,
            days_rest,
            pitches_last_7_days,
            ups_last_7_days,
            appearances_last_7_days,
            pitched_previous_day,
            pitched_two_consecutive_days
        FROM pitcher_workload
        WHERE pitcher_id = 10 AND game_date = DATE '2024-06-08'
        """
    ).fetchone()

    assert row == (None, None, 0, 0, 0, False, False)


def test_same_day_appearances_are_aggregated_but_not_treated_as_history(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    june_9_rows = workload_connection.sql(
        """
        SELECT
            game_pk,
            previous_appearance_date,
            pitches_previous_day,
            appearances_previous_day
        FROM pitcher_workload
        WHERE pitcher_id = 30 AND game_date = DATE '2024-06-09'
        ORDER BY game_pk
        """
    ).fetchall()
    june_10_row = workload_connection.sql(
        """
        SELECT pitches_previous_day, appearances_previous_day
        FROM pitcher_workload
        WHERE pitcher_id = 30 AND game_date = DATE '2024-06-10'
        """
    ).fetchone()

    assert june_9_rows == [
        (302, date(2024, 6, 8), 5, 1),
        (303, date(2024, 6, 8), 5, 1),
    ]
    assert june_10_row == (15, 2)


def test_season_to_date_workload_excludes_current_appearance_and_crosses_teams(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    rows = workload_connection.sql(
        """
        SELECT
            game_pk, is_start, season_appearance_number,
            season_appearances_before, season_pitches_before,
            season_outs_before, season_ip_before, season_ups_before
        FROM pitcher_workload
        WHERE pitcher_id = 10 AND season = 2024
        ORDER BY game_date, game_pk
        """
    ).fetchall()

    assert rows[0] == (101, False, 1, 0, 0, 0, 0.0, 0)
    assert rows[2] == pytest.approx((103, True, 3, 2, 35, 7, 7 / 3, 3))
    # The June 10 start contributes to workload before the June 11 relief outing.
    assert rows[3] == (104, False, 4, 3, 45, 10, 10 / 3, 4)


def test_season_to_date_workload_resets_between_seasons(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    row = workload_connection.sql(
        """
        SELECT
            season_appearance_number, season_appearances_before,
            season_pitches_before, season_outs_before,
            season_ip_before, season_ups_before
        FROM pitcher_workload
        WHERE pitcher_id = 10 AND season = 2025
        """
    ).fetchone()

    assert row == (1, 0, 0, 0, 0.0, 0)


def test_supports_custom_source_and_output_view_names(
    workload_connection: duckdb.DuckDBPyConnection,
) -> None:
    workload_connection.execute(
        "CREATE TEMP VIEW custom_appearances AS SELECT * FROM pitcher_appearances"
    )

    create_pitcher_workload_view(
        workload_connection,
        view_name="custom_workload",
        appearances_view_name="custom_appearances",
    )

    assert workload_connection.sql(
        "SELECT count(*) FROM custom_workload"
    ).fetchone() == (12,)


@pytest.mark.parametrize("parameter", ["view_name", "appearances_view_name"])
def test_rejects_unsafe_view_names(
    workload_connection: duckdb.DuckDBPyConnection,
    parameter: str,
) -> None:
    with pytest.raises(ValueError, match="simple SQL identifier"):
        create_pitcher_workload_view(
            workload_connection,
            **{parameter: "workload; DROP TABLE pitcher_appearances"},
        )
