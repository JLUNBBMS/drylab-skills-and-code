# Task 1 Delivery Model Code

`run_all.py` coordinates calibration, baseline simulation, secondary endpoints, uncertainty analysis, decision analysis, figures, and report generation. The implementation is in `src/`.

The model expects processed inputs under `data/processed/` and writes generated artifacts to `results/`, `figures/`, and `output/`. Those data and generated artifacts are distributed through GitLab rather than this GitHub code package.

Run from this directory after restoring the matching GitLab data release:

```text
python run_all.py
```
