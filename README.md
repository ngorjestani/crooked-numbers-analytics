# Crooked Numbers Analytics

Research and analytical code for the Crooked Numbers baseball analytics project.
This repository is intentionally separate from both Statcast ingestion and the
eventual application/API. Its initial research focus will be managerial pitching
strategy and bullpen usage, but that analysis has not been implemented yet.

Azure Blob Storage remains the source of truth. Research uses a disposable local
copy so repeated notebook queries stay fast:

```text
Statcast ingestion
        ↓
Azure Blob Storage (source of truth)
        ↓
sync_statcast.py
        ↓
data/raw/statcast/ (local disposable cache)
        ↓
DuckDB
        ↓
Jupyter research
```

## Local setup

Python 3.12 is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
ruff check .
jupyter lab
```

Set `AZURE_STORAGE_ACCOUNT_URL` in `.env` to an HTTPS Blob Storage account URL,
such as `https://example.blob.core.windows.net`. The default container is
`baseball-data`. `ANALYTICS_DATA_ROOT` defaults to `./data`, resolved from the
repository root even when Jupyter starts in another directory. The local `.env`
file is ignored by Git.

Authenticate through a source supported by `DefaultAzureCredential`, such as
`az login`, environment credentials, workload identity, or managed identity.
Synchronize the initial research seasons:

```bash
python scripts/sync_statcast.py --season 2023 --season 2024
```

Existing files are skipped. Pass `--overwrite` to download them again. The
script only reads the requested `raw/statcast/season=YYYY/` prefixes and
preserves their partition structure below `data/`.

Notebooks then query the local Parquet cache with an ordinary in-memory DuckDB
connection:

```python
from crooked_numbers_analytics.db import open_database
from crooked_numbers_analytics.paths import dataset_path

path = dataset_path(
    "raw/statcast/season=*/game_date=*/statcast.parquet",
)

with open_database() as connection:
    rows = connection.execute("SELECT count(*) FROM read_parquet(?)", [path]).fetchone()
```

The entire `data/` directory is intentionally ignored by Git. It is a disposable
research cache and can be recreated from Azure at any time. The workflow does
not create a persistent database or upload anything to Azure.

## Development

Keep reusable configuration and query functionality in the
`crooked_numbers_analytics` package. Use notebooks for exploration and promote
logic into the package once it becomes useful beyond a single experiment.
