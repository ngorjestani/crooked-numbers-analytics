"""Derive pre-appearance pitching workload from pitcher appearances."""

from __future__ import annotations

import re

import duckdb

_VIEW_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def create_pitcher_workload_view(
    con: duckdb.DuckDBPyConnection,
    *,
    view_name: str = "pitcher_workload",
    appearances_view_name: str = "pitcher_appearances",
) -> None:
    """Create a temporary view with workload entering each appearance.

    Workload windows contain prior calendar dates only. For example, an
    appearance on June 10 has a two-day window of June 8-9; June 10 is never
    included. ``days_rest`` is the number of full off-days since the latest
    earlier appearance date, so June 9 to June 10 produces zero days of rest.

    Multiple appearances on one date are combined in the daily history. All
    appearances on that date receive the same workload from earlier dates;
    same-day games are not treated as previous-day work or ordered relative to
    one another for acute windows. Season-to-date fields use deterministic
    ``game_date, game_pk`` ordering within pitcher and season. ``game_pk`` is a
    stable tie-breaker, but is not claimed to be first-pitch chronology for a
    same-day doubleheader.
    """

    _validate_view_name(view_name, "view_name")
    _validate_view_name(appearances_view_name, "appearances_view_name")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW {view_name} AS
        WITH daily_appearances AS (
            SELECT
                pitcher_id,
                game_date,
                sum(pitch_count) AS pitches,
                sum(ups) AS ups,
                count(*) AS appearances
            FROM {appearances_view_name}
            WHERE pitcher_id IS NOT NULL
            GROUP BY pitcher_id, game_date
        ),
        daily_workload AS (
            SELECT
                pitcher_id,
                game_date,
                lag(game_date) OVER pitcher_dates AS previous_appearance_date,
                coalesce(
                    sum(pitches) OVER previous_day,
                    0
                ) AS pitches_previous_day,
                coalesce(sum(pitches) OVER last_2_days, 0) AS pitches_last_2_days,
                coalesce(sum(pitches) OVER last_3_days, 0) AS pitches_last_3_days,
                coalesce(sum(pitches) OVER last_7_days, 0) AS pitches_last_7_days,
                coalesce(sum(ups) OVER previous_day, 0) AS ups_previous_day,
                coalesce(sum(ups) OVER last_2_days, 0) AS ups_last_2_days,
                coalesce(sum(ups) OVER last_3_days, 0) AS ups_last_3_days,
                coalesce(sum(ups) OVER last_7_days, 0) AS ups_last_7_days,
                coalesce(
                    sum(appearances) OVER previous_day,
                    0
                ) AS appearances_previous_day,
                coalesce(
                    sum(appearances) OVER last_2_days,
                    0
                ) AS appearances_last_2_days,
                coalesce(
                    sum(appearances) OVER last_3_days,
                    0
                ) AS appearances_last_3_days,
                coalesce(
                    sum(appearances) OVER last_7_days,
                    0
                ) AS appearances_last_7_days,
                coalesce(sum(appearances) OVER two_days_ago, 0)
                    AS appearances_two_days_ago
            FROM daily_appearances
            WINDOW
                pitcher_dates AS (
                    PARTITION BY pitcher_id ORDER BY game_date
                ),
                previous_day AS (
                    pitcher_dates RANGE BETWEEN INTERVAL 1 DAY PRECEDING
                    AND INTERVAL 1 DAY PRECEDING
                ),
                two_days_ago AS (
                    pitcher_dates RANGE BETWEEN INTERVAL 2 DAYS PRECEDING
                    AND INTERVAL 2 DAYS PRECEDING
                ),
                last_2_days AS (
                    pitcher_dates RANGE BETWEEN INTERVAL 2 DAYS PRECEDING
                    AND INTERVAL 1 DAY PRECEDING
                ),
                last_3_days AS (
                    pitcher_dates RANGE BETWEEN INTERVAL 3 DAYS PRECEDING
                    AND INTERVAL 1 DAY PRECEDING
                ),
                last_7_days AS (
                    pitcher_dates RANGE BETWEEN INTERVAL 7 DAYS PRECEDING
                    AND INTERVAL 1 DAY PRECEDING
                )
        ),
        cumulative_workload AS (
            SELECT
                source_appearance.*,
                row_number() OVER season_appearances
                    AS season_appearance_number,
                row_number() OVER season_appearances - 1
                    AS season_appearances_before,
                coalesce(
                    sum(pitch_count) OVER season_before,
                    0
                ) AS season_pitches_before,
                coalesce(
                    sum(outs_recorded) OVER season_before,
                    0
                ) AS season_outs_before,
                coalesce(
                    sum(outs_recorded) OVER season_before,
                    0
                ) / 3.0 AS season_ip_before,
                coalesce(
                    sum(ups) OVER season_before,
                    0
                ) AS season_ups_before
            FROM {appearances_view_name} AS source_appearance
            WINDOW
                season_appearances AS (
                    PARTITION BY pitcher_id, season
                    ORDER BY game_date, game_pk
                ),
                season_before AS (
                    season_appearances ROWS BETWEEN UNBOUNDED PRECEDING
                    AND 1 PRECEDING
                )
        )
        SELECT
            appearance.*,
            workload.previous_appearance_date,
            CASE
                WHEN workload.previous_appearance_date IS NOT NULL
                THEN date_diff(
                    'day',
                    workload.previous_appearance_date,
                    appearance.game_date
                ) - 1
            END AS days_rest,
            coalesce(workload.pitches_previous_day, 0) AS pitches_previous_day,
            coalesce(workload.pitches_last_2_days, 0) AS pitches_last_2_days,
            coalesce(workload.pitches_last_3_days, 0) AS pitches_last_3_days,
            coalesce(workload.pitches_last_7_days, 0) AS pitches_last_7_days,
            coalesce(workload.ups_previous_day, 0) AS ups_previous_day,
            coalesce(workload.ups_last_2_days, 0) AS ups_last_2_days,
            coalesce(workload.ups_last_3_days, 0) AS ups_last_3_days,
            coalesce(workload.ups_last_7_days, 0) AS ups_last_7_days,
            coalesce(workload.appearances_previous_day, 0)
                AS appearances_previous_day,
            coalesce(workload.appearances_last_2_days, 0)
                AS appearances_last_2_days,
            coalesce(workload.appearances_last_3_days, 0)
                AS appearances_last_3_days,
            coalesce(workload.appearances_last_7_days, 0)
                AS appearances_last_7_days,
            coalesce(workload.appearances_previous_day, 0) > 0
                AS pitched_previous_day,
            coalesce(workload.appearances_previous_day, 0) > 0
                AND coalesce(workload.appearances_two_days_ago, 0) > 0
                AS pitched_two_consecutive_days
        FROM cumulative_workload AS appearance
        LEFT JOIN daily_workload AS workload
            ON appearance.pitcher_id = workload.pitcher_id
            AND appearance.game_date = workload.game_date
        """
    )


def _validate_view_name(value: str, parameter: str) -> None:
    if not _VIEW_NAME_PATTERN.fullmatch(value):
        raise ValueError(f"{parameter} must be a simple SQL identifier")
