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
    case. ``innings_appeared`` and ``ups`` both count distinct innings containing
    a Statcast record; they do not infer unrecorded warmup activity.

    Plate-appearance results use terminal rows (non-null ``events``), excluding
    incomplete ``truncated_pa`` records. Outs primarily use changes in Statcast's
    ``outs_when_up`` state, which captures runner outs as well as batter events;
    explicit event values handle incomplete state and final-play edge cases. Rare
    scoring cases such as suspended games or a mid-plate-appearance pitching
    change should still be validated against official records.

    Strikes include called/automatic strikes, swings and misses, fouls, and balls
    put in play. Swings include misses, fouls, and balls put in play; whiffs include
    swinging strikes and missed bunts. Fastball velocity is intentionally limited
    to four-seam fastballs (``pitch_type = 'FF'``), not sinkers or cutters.
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
                inning_topbot,
                at_bat_number,
                pitch_number,
                outs_when_up,
                post_home_score,
                post_away_score,
                events,
                description,
                pitch_type,
                release_speed,
                launch_speed,
                launch_speed_angle,
                events IS NOT NULL AND events <> 'truncated_pa'
                    AS is_terminal_pa,
                CASE
                    WHEN events IN (
                        'double_play',
                        'grounded_into_double_play',
                        'sac_bunt_double_play',
                        'sac_fly_double_play',
                        'strikeout_double_play'
                    ) THEN 2
                    WHEN events = 'triple_play' THEN 3
                    WHEN events IN (
                        'field_out',
                        'fielders_choice',
                        'fielders_choice_out',
                        'force_out',
                        'sac_bunt',
                        'sac_fly',
                        'strikeout'
                    ) THEN 1
                    ELSE 0
                END AS event_outs,
                description IN (
                    'automatic_strike',
                    'bunt_foul_tip',
                    'called_strike',
                    'foul',
                    'foul_bunt',
                    'foul_pitchout',
                    'foul_tip',
                    'hit_into_play',
                    'missed_bunt',
                    'swinging_pitchout',
                    'swinging_strike',
                    'swinging_strike_blocked'
                ) AS is_strike,
                description IN (
                    'bunt_foul_tip',
                    'foul',
                    'foul_bunt',
                    'foul_pitchout',
                    'foul_tip',
                    'hit_into_play',
                    'missed_bunt',
                    'swinging_pitchout',
                    'swinging_strike',
                    'swinging_strike_blocked'
                ) AS is_swing,
                description IN (
                    'missed_bunt',
                    'swinging_pitchout',
                    'swinging_strike',
                    'swinging_strike_blocked'
                ) AS is_whiff
            FROM read_parquet(
                [{path_list}],
                hive_partitioning = true,
                union_by_name = true
            )
            WHERE game_type = {game_type_literal}
        ),
        sequenced_pitches AS (
            SELECT
                *,
                lead(outs_when_up) OVER half_inning AS next_outs_same_half,
                lead(at_bat_number) OVER half_inning AS next_at_bat_same_half,
                lead(game_pk) OVER game_pitches AS next_game_pitch
            FROM source_pitches
            WINDOW
                half_inning AS (
                    PARTITION BY game_pk, inning, inning_topbot
                    ORDER BY at_bat_number, pitch_number, pitcher_id
                ),
                game_pitches AS (
                    PARTITION BY game_pk
                    ORDER BY at_bat_number, pitch_number, pitcher_id
                )
        ),
        scored_pitches AS (
            SELECT
                *,
                CASE
                    WHEN outs_when_up IS NULL THEN event_outs
                    WHEN next_at_bat_same_half IS NOT NULL THEN coalesce(
                        greatest(next_outs_same_half - outs_when_up, 0),
                        event_outs
                    )
                    WHEN next_game_pitch IS NOT NULL
                        THEN greatest(3 - outs_when_up, 0)
                    WHEN inning_topbot = 'Top'
                        THEN greatest(3 - outs_when_up, 0)
                    WHEN post_home_score <= post_away_score
                        THEN greatest(3 - outs_when_up, 0)
                    ELSE event_outs
                END AS outs_on_pitch
            FROM sequenced_pitches
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
            FROM scored_pitches
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
                count(DISTINCT inning) AS innings_appeared,
                count(DISTINCT inning) AS ups,
                sum(outs_on_pitch) AS outs_recorded,
                sum(outs_on_pitch) / 3.0 AS innings_pitched,
                count(DISTINCT at_bat_number)
                    FILTER (WHERE is_terminal_pa) AS batters_faced,
                count(DISTINCT at_bat_number)
                    FILTER (WHERE events IN (
                        'strikeout', 'strikeout_double_play'
                    )) AS strikeouts,
                count(DISTINCT at_bat_number)
                    FILTER (WHERE events IN ('walk', 'intent_walk')) AS walks,
                count(DISTINCT at_bat_number)
                    FILTER (WHERE events IN (
                        'single', 'double', 'triple', 'home_run'
                    )) AS hits,
                count(DISTINCT at_bat_number)
                    FILTER (WHERE events = 'home_run') AS home_runs,
                count(*) FILTER (WHERE is_strike) AS strikes,
                count(*) FILTER (WHERE is_strike) / count(*)::DOUBLE
                    AS strike_rate,
                count(*) FILTER (WHERE is_swing) AS swings,
                count(*) FILTER (WHERE is_whiff) AS whiffs,
                count(*) FILTER (WHERE is_whiff)
                    / nullif(count(*) FILTER (WHERE is_swing), 0)::DOUBLE
                    AS whiff_rate,
                count(*) FILTER (WHERE description = 'called_strike')
                    AS called_strikes,
                count(*) FILTER (
                    WHERE description = 'called_strike' OR is_whiff
                ) AS csw,
                count(*) FILTER (
                    WHERE description = 'called_strike' OR is_whiff
                ) / count(*)::DOUBLE AS csw_rate,
                count(*) FILTER (WHERE pitch_type = 'FF') AS fastball_pitches,
                avg(release_speed) FILTER (WHERE pitch_type = 'FF')
                    AS avg_fastball_velocity,
                max(release_speed) FILTER (WHERE pitch_type = 'FF')
                    AS max_fastball_velocity,
                count(*) FILTER (WHERE description = 'hit_into_play')
                    AS balls_in_play,
                count(*) FILTER (
                    WHERE description = 'hit_into_play'
                      AND launch_speed IS NOT NULL
                ) AS exit_velocity_balls,
                avg(launch_speed) FILTER (
                    WHERE description = 'hit_into_play'
                ) AS avg_exit_velocity,
                max(launch_speed) FILTER (
                    WHERE description = 'hit_into_play'
                ) AS max_exit_velocity,
                count(*) FILTER (
                    WHERE description = 'hit_into_play'
                      AND launch_speed >= 95
                ) AS hard_hit_count,
                count(*) FILTER (
                    WHERE description = 'hit_into_play'
                      AND launch_speed >= 95
                ) / nullif(
                    count(*) FILTER (
                        WHERE description = 'hit_into_play'
                          AND launch_speed IS NOT NULL
                    ),
                    0
                )::DOUBLE AS hard_hit_rate,
                count(*) FILTER (
                    WHERE description = 'hit_into_play'
                      AND launch_speed_angle IS NOT NULL
                ) AS barrel_eligible_balls,
                count(*) FILTER (
                    WHERE description = 'hit_into_play'
                      AND launch_speed_angle = 6
                ) AS barrel_count,
                count(*) FILTER (
                    WHERE description = 'hit_into_play'
                      AND launch_speed_angle = 6
                ) / nullif(
                    count(*) FILTER (
                        WHERE description = 'hit_into_play'
                          AND launch_speed_angle IS NOT NULL
                    ),
                    0
                )::DOUBLE AS barrel_rate,
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
            last_inning,
            innings_appeared,
            ups,
            outs_recorded,
            innings_pitched,
            batters_faced,
            strikeouts,
            walks,
            hits,
            home_runs,
            strikes,
            strike_rate,
            swings,
            whiffs,
            whiff_rate,
            called_strikes,
            csw,
            csw_rate,
            fastball_pitches,
            avg_fastball_velocity,
            max_fastball_velocity,
            balls_in_play,
            exit_velocity_balls,
            avg_exit_velocity,
            max_exit_velocity,
            hard_hit_count,
            hard_hit_rate,
            barrel_eligible_balls,
            barrel_count,
            barrel_rate
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
