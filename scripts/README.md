# Research Scripts

Use this directory for small executable scripts that inspect datasets, test
queries, check assumptions, or perform one-off research tasks.

Scripts should import reusable configuration, database setup, and analytical code
from `crooked_numbers_analytics` instead of duplicating it. Install the project in
editable mode with `pip install -e ".[dev]"` so scripts can use normal package
imports.
