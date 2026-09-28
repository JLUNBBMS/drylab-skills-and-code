# External Data Location

The data and archived outputs for this source release are maintained in:

<https://gitlab.com/jlunbbms-group/drylab-data-and-modeling>

Use the `delivery-model/` directory from that repository. The runner expects the following files relative to this GitHub source directory:

```text
data/reference_inputs.json
data/calibration_0927-3/reference_summary.json
results/summary.json
```

For a complete local reproduction, copy both GitLab directories below into this directory:

```text
delivery-model/data/    -> data/
delivery-model/results/ -> results/
```

Generated files are written to `reproduced/` by default and should not be committed to this source repository.
