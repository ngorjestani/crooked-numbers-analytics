# Crooked Numbers Analytics

Research and analytical code for the Crooked Numbers baseball analytics project.
This repository is intentionally separate from both Statcast ingestion and the
eventual application/API. Its initial research focus will be managerial pitching
strategy and bullpen usage, but that analysis has not been implemented yet.

The initial data workflow reads Parquet datasets directly from Azure Blob Storage:

```text
Azure Blob Parquet
        ↓
DuckDB + Python
        ↓
Jupyter research / reusable analytics
        ↓
future derived datasets or application outputs
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
`baseball-data`. The local `.env` file is ignored by Git.

When an account URL is configured, `open_database()` loads DuckDB's Azure
extension and creates a temporary credential-chain secret. Authenticate through
a supported Azure credential source, such as `az login`, environment credentials,
workload identity, or managed identity. DuckDB can then query datasets directly:

```python
from crooked_numbers_analytics import Settings, azure_dataset_path, open_database

settings = Settings.from_env()
path = azure_dataset_path("raw/statcast/**/*.parquet", settings.azure_storage_container)

with open_database(settings) as connection:
    rows = connection.execute("SELECT count(*) FROM read_parquet(?)", [path]).fetchone()
```

No local synchronization, persistent database, tables, or views are created.

## Development

Keep reusable configuration and query functionality in the
`crooked_numbers_analytics` package. Use notebooks for exploration and promote
logic into the package once it becomes useful beyond a single experiment.
