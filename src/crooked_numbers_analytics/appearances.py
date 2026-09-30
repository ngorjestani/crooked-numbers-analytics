"""Derive pitching appearances from locally synchronized Statcast data."""

from __future__ import annotations

import re
from collections.abc import Iterable

import duckdb

from crooked_numbers_analytics.paths import dataset_path

_VIEW_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def create_pitcher_appearances_view(
    con: duckdb.DuckDBPyConnection,
    *,
    view_name: str = "pitcher_appearances",
    seasons: Iterable[int] | None = None,
    game_type: str = "R",
) -> None:
    """Create a temporary view containing one row per pitcher, team, and game.

    Regular-season games (``game_type = 'R'``) are included by default. Passing
    ``seasons`` narrows the Parquet paths themselves, allowing DuckDB to target
    only those Hive partitions.

    ``pitch_count`` counts Statcast pitch records. It should be validated against
    official pitch counts before perfect equivalence is assumed in every edge
    case.
    """

    if not _VIEW_NAME_PATTERN.fullmatch(view_name):
        raise ValueError("view_name must be a simple SQL identifier")
    if not game_type:
        raise ValueError("game_type must not be empty")

    parquet_paths = _statcast_paths(seasons)
    path_list = ", ".join(_sql_string(path) for path in parquet_paths)
    game_type_literal = _sql_string(game_type)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW {view_name} AS
        WITH source_pitches AS (
            SELECT
                game_pk,
                game_date,
                season,
                CASE
                    WHEN inning_topbot = 'Top' THEN home_team
                    WHEN inning_topbot = 'Bot' THEN away_team
                    ELSE error(
                        'Unexpected inning_topbot value: '
                        || coalesce(inning_topbot, 'NULL')
                    )
                END AS pitching_team,
                pitcher AS pitcher_id,
                player_name AS pitcher_name,
                inning,
                at_bat_number,
                pitch_number
            FROM read_parquet(
                [{path_list}],
                hive_partitioning = true,
                union_by_name = true
            )
            WHERE game_type = {game_type_literal}
        ),
        ordered_pitches AS (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY game_pk, pitching_team
                    ORDER BY
                        at_bat_number NULLS LAST,
                        pitch_number NULLS LAST,
                        pitcher_id NULLS LAST
                ) AS game_pitch_order
            FROM source_pitches
        ),
        appearances AS (
            SELECT
                game_pk,
                min(game_date) AS game_date,
                min(season) AS season,
                pitching_team,
                pitcher_id,
                first(pitcher_name ORDER BY game_pitch_order)
                    FILTER (WHERE pitcher_name IS NOT NULL) AS pitcher_name,
                count(*) AS pitch_count,
                min(inning) AS first_inning,
                max(inning) AS last_inning,
                min(game_pitch_order) AS first_pitch_order
            FROM ordered_pitches
            GROUP BY game_pk, pitching_team, pitcher_id
        ),
        classified_appearances AS (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY game_pk, pitching_team
                    ORDER BY first_pitch_order, pitcher_id NULLS LAST
                ) = 1 AS is_start
            FROM appearances
        )
        SELECT
            game_pk,
            game_date,
            season,
            pitching_team,
            pitcher_id,
            pitcher_name,
            is_start,
            pitch_count,
            first_inning,
            last_inning
        FROM classified_appearances
        """
    )


def _statcast_paths(seasons: Iterable[int] | None) -> list[str]:
    if seasons is None:
        return [dataset_path("raw/statcast/season=*/game_date=*/statcast.parquet")]

    requested_seasons = list(seasons)
    if not requested_seasons:
        raise ValueError("seasons must contain at least one season")
    if any(
        isinstance(season, bool) or not isinstance(season, int)
        for season in requested_seasons
    ):
        raise TypeError("seasons must contain only integers")
    normalized_seasons = sorted(set(requested_seasons))

    return [
        dataset_path(
            f"raw/statcast/season={season}/game_date=*/statcast.parquet"
        )
        for season in normalized_seasons
    ]


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
