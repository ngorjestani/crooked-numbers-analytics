# Notebooks

Use this directory for exploratory baseball research. Notebooks should import
reusable functionality from `crooked_numbers_analytics` rather than accumulating
permanent configuration, data-access, or analytical logic in notebook cells.

The intended workflow is:

```text
research question
      ↓
Jupyter exploration
      ↓
repeatable/useful logic identified
      ↓
move reusable logic into src/crooked_numbers_analytics
      ↓
add tests
      ↓
reuse from notebooks/scripts
```

Temporary code and queries are expected during exploration. Important calculations
should move into the package once they become useful or repeatable.

Start JupyterLab from the repository root after installing the development
dependencies:

```bash
pip install -e ".[dev]"
jupyter lab
```
