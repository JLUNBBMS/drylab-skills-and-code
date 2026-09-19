# Virtual Fermenter Source Code

This directory contains the source code for a three-state virtual-fermenter model of biomass, glucose, and Compound K, together with Bayesian optimization and Pareto-front analysis.

## Files

| File | Purpose |
|---|---|
| `run_all.py` | Runs the core simulation and optimization scripts |
| `src/virtual_fermenter_v2.py` | Three-state model, single-point anchoring, grid search, and comparison plot generation |
| `src/bo_pareto_v2.py` | Bayesian optimization and Pareto-front analysis |
| `src/make_wiki_figures.py` | Generates explanatory model figures |

## Installation

```text
python -m pip install -r requirements.txt
```

Run from this directory:

```text
python run_all.py
```

The released input record, parameter provenance, result tables, and reviewed figures belong in GitLab. Before using generated plots publicly, the team should confirm that the baseline and round-2 comparison uses one consistent endpoint definition.
