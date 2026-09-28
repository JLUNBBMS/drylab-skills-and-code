# TH21 tFNA Skin Delivery Model

This directory contains the source code for the current 0927-4 delivery-model release. The model represents a finite follicular reservoir, transport through viable epidermis and shallow dermis, cellular uptake, and loss of intact carrier after a 15-minute application.

## Source layout

| Path | Purpose |
|---|---|
| `src/run_0927_4.py` | Runs the calculation, numerical checks, result-table export, and four updated figures |
| `src/model.py` | Defines the follicular reservoir, tissue transport, uptake, and carrier-loss equations |
| `src/physics.py` | Defines physical inputs and derived transport quantities |
| `src/figure_style.py` | Defines plotting styles and the model schematic |
| `requirements.txt` | Pins the Python packages used for the verified release |
| `DATA_LOCATION.md` | Identifies the external inputs and reference results stored in GitLab |

## Data setup

Model inputs, calibration records, archived numerical results, and released figures are stored in the companion GitLab repository:

<https://gitlab.com/jlunbbms-group/drylab-data-and-modeling>

Before running the model, copy the GitLab `delivery-model/data/` and `delivery-model/results/` directories into this directory. See `DATA_LOCATION.md` for the required paths.

## Run

Use Python 3.12 and run:

```text
python -m pip install -r requirements.txt
python src/run_0927_4.py
```

The default output directory is `reproduced/`. A different directory can be supplied with `--output-dir`.

The runner checks mass conservation, non-negative states, termination of external input after mask removal, agreement with the retained 15-minute calibration endpoint, and agreement with the archived summary values.

## Evidence boundary

The generated concentrations, retention values, time series, and figures are model outputs. They are not experimental measurements or experimental validation.
