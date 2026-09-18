"""Synchronize selected Statcast seasons from Azure Blob Storage."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient

from crooked_numbers_analytics.paths import (
    STATCAST_PREFIX,
    local_path_for_statcast_blob,
)
from crooked_numbers_analytics.settings import Settings, get_settings


def sync_statcast(
    seasons: Sequence[int],
    settings: Settings,
    *,
    overwrite: bool = False,
) -> tuple[int, int]:
    """Download requested Statcast season prefixes and return download/skip counts."""

    credential = DefaultAzureCredential()
    container = ContainerClient(
        account_url=settings.azure_storage_account_url,
        container_name=settings.azure_storage_container,
        credential=credential,
    )
    downloaded = 0
    skipped = 0

    for season in dict.fromkeys(seasons):
        prefix = f"{STATCAST_PREFIX}/season={season}/"
        print(f"Syncing {prefix}")

        try:
            blobs = container.list_blobs(name_starts_with=prefix)
            for blob in blobs:
                if not blob.name.endswith(".parquet"):
                    continue

                destination = local_path_for_statcast_blob(
                    blob.name,
                    settings.analytics_data_root,
                )
                if destination.exists() and not overwrite:
                    skipped += 1
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".part")
                print(f"  download {blob.name}")
                try:
                    with temporary.open("wb") as output:
                        container.get_blob_client(blob.name).download_blob().readinto(
                            output
                        )
                    temporary.replace(destination)
                except Exception as exc:
                    temporary.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"failed to download {blob.name}: {exc}"
                    ) from exc
                downloaded += 1
        except (AzureError, OSError) as exc:
            raise RuntimeError(f"failed while syncing {prefix}: {exc}") from exc

    return downloaded, skipped


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Statcast Parquet files to the local research cache."
    )
    parser.add_argument(
        "--season",
        action="append",
        required=True,
        type=_season,
        help="season to synchronize; repeat for multiple seasons",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="redownload files that already exist locally",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        settings = get_settings()
        downloaded, skipped = sync_statcast(
            args.season,
            settings,
            overwrite=args.overwrite,
        )
    except (AzureError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Complete: downloaded {downloaded}, skipped {skipped} existing files")
    return 0


def _season(value: str) -> int:
    try:
        season = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("season must be a four-digit year") from exc
    if not 1000 <= season <= 9999:
        raise argparse.ArgumentTypeError("season must be a four-digit year")
    return season


if __name__ == "__main__":
    raise SystemExit(main())
