# Delivery and Release Model Source Code

This directory contains two source-code modules:

| Path | Purpose |
|---|---|
| `task1_delivery_model/` | Comparative delivery model, calibration, uncertainty analysis, decisions, plots, and reports |
| `task1b_release_model/` | Release-curve analysis, quality checks, candidate screening, and workbook construction |

Install the shared Python dependencies with:

```text
python -m pip install -r requirements.txt
```

Project datasets and generated results are maintained in GitLab. Place them in the paths described by the module-level `DATA_LOCATION.md` files before running workflows that require those files.

The JavaScript artifact-rendering helpers require their original rendering environment; the core scientific analysis is implemented in Python.
