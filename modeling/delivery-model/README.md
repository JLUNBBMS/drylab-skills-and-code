# TH21 tFNA Skin Delivery Model

This directory contains the source code for the 0927-4 delivery-model release, including the plotting revision delivered on 2026-10-04. The model represents a finite follicular reservoir, transport through viable epidermis and shallow dermis, cellular uptake, and loss of intact carrier after a 15-minute application.

The supplied design input treats 1 µmol/L CK as an upper concentration limit and converts it to a 0.5 µmol/L tFNA limit at two CK molecules per carrier. The `target_uM` field retains its existing name but represents that converted limit. This is a team-supplied modeling constraint; the calculation does not establish biological safety.

## Source layout

| Path | Purpose |
|---|---|
| `src/run_0927_4.py` | Runs the calculation, numerical checks, result-table export, and four updated figures |
| `src/model.py` | Defines the follicular reservoir, tissue transport, uptake, and carrier-loss equations |
| `src/physics.py` | Defines physical inputs and derived transport quantities |
| `src/figure_style.py` | Defines plotting styles and the model schematic |
| `src/plot_depth_heatmap.py` | Defines the time-depth heatmap and cell-contact curves for report Figure 5; imported by the main runner |
| `requirements.txt` | Lists the pinned Python dependencies supplied with the release |
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

The main runner generates report Figures 2, 4, 5, and 6. Figure 5 is saved as `Fig04_Depth_and_Delayed_Exposure_Heatmap.png` and `.svg`; it combines a 0-4-hour time-depth heatmap with layer-mean cell-contact concentration curves and marks cessation of dosing at 15 minutes. The filename retains its original numbering prefix; `figure_manifest.md` in GitLab maps files to report figure numbers.

The runner checks mass conservation, non-negative states, termination of external input after mask removal, agreement with the retained 15-minute calibration endpoint, and agreement with the archived summary values.

## Standalone heatmap export

To regenerate the archived heatmap table on a uniform 30-second grid, run:

```text
python src/plot_depth_heatmap.py
```

This script checks the archived depth profiles at 15 minutes, 1 hour, and 4 hours, then writes `results/depth_time_heatmap.csv`. As supplied, it saves the PNG/SVG heatmap to both this model directory's `images/` directory and its parent directory's `images/` directory. It does not accept `--output-dir`. Use a separate local reproduction directory when regenerating the archived table or figures.

The main runner uses its own time grid for the heatmap and writes its figures under the selected output directory; it does not export `depth_time_heatmap.csv`.

## Evidence boundary

The generated concentrations, retention values, time series, and figures are model outputs. They are not experimental measurements or experimental validation.
