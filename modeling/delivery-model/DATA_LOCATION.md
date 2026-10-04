# External Data Location

The data and archived outputs for this source release are maintained in:

<https://gitlab.com/jlunbbms-group/drylab-data-and-modeling>

Use the `delivery-model/` directory from that repository. The runner expects the following files relative to this GitHub source directory:

```text
data/reference_inputs.json
data/calibration_0927-3/reference_summary.json
results/summary.json
```

The standalone `src/plot_depth_heatmap.py` script additionally reads:

```text
results/depth_profiles.csv
```

For a complete local reproduction, copy both GitLab directories below into this directory:

```text
delivery-model/data/    -> data/
delivery-model/results/ -> results/
```

Use the companion data and results from the plotting revision delivered on 2026-10-04. The source entry point keeps its filename `run_0927_4.py`.

The main runner writes generated files to `reproduced/` by default. The standalone heatmap script writes `results/depth_time_heatmap.csv` and image files in two local `images/` directories, as described in `README.md`. Generated data and figures belong in the GitLab data repository and should not be committed to this source repository.
