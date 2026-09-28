# Dry Lab Skills and Source Code

This repository contains the team's reusable dry-lab skills and source code.
Project datasets, fitted parameters, numerical result tables, and released model figures are maintained in GitLab and are not duplicated here.

## Repository layout

| Path | Contents |
|---|---|
| `skills/generate-cadnano/` | generate-cadnano skill instructions, Python implementation, tests, and references |
| `skills/pymol-deepseek-plugin/` | PyMOL DeepSeek plugin source, tests, release checks, and project documentation |
| `modeling/virtual-fermenter/` | Virtual-fermenter model and optimization source code |
| `modeling/delivery-model/` | Current TH21 tFNA skin-delivery model source code and reproduction entry point |

## Data location

Model data and results are maintained in the companion [GitLab data repository](https://gitlab.com/jlunbbms-group/drylab-data-and-modeling). Each modeling directory contains a `DATA_LOCATION.md` file describing the expected external data or result directories.

## Evidence boundaries

- Generated model values and figures are computational outputs, not experimental validation.
- Synthetic or demonstration inputs must remain labeled as synthetic.
- The validation status of each skill or model is documented within its own directory.

## Before public release

The team must select and add an appropriate repository license.
