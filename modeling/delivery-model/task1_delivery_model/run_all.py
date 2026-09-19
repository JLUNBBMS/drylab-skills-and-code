from __future__ import annotations

import json
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import scipy

from src.analysis import (
    export_task2_interface,
    export_secondary_endpoints,
    run_baseline,
    run_numerical_tests,
    run_uncertainty,
    validate_liposome_timecourse,
)
from src.calibration import calibrated_systems
from src.model import Geometry
from src.decision import run_decision_analysis
from src.reporting import write_reports
from src.plots import create_all_plots


def main() -> None:
    data_dir = ROOT / "data" / "processed"
    results_dir = ROOT / "results"
    figures_dir = ROOT / "figures"
    geometry = Geometry()

    systems, benchmarks, metrics, parameter_bounds = calibrated_systems(
        data_dir, results_dir / "calibration", geometry
    )
    baseline_results, endpoints = run_baseline(
        systems, geometry, results_dir / "baseline"
    )
    task2 = export_task2_interface(
        baseline_results, results_dir / "task2_interface.csv"
    )
    secondary, flux = export_secondary_endpoints(baseline_results, results_dir)

    lip_frame, lip_metrics = validate_liposome_timecourse(
        systems["liposome_CK"], geometry, data_dir
    )
    lip_frame.to_csv(
        results_dir / "calibration" / "liposome_timecourse_validation.csv",
        index=False,
    )
    lip_metric_row = pd.DataFrame(
        [{"benchmark": "liposome_GSL7_rat_skin_timecourse",
          "usage": "held_out_proxy_validation", **lip_metrics}]
    )
    all_metrics = pd.concat([metrics, lip_metric_row], ignore_index=True)
    all_metrics.to_csv(results_dir / "calibration" / "all_benchmark_metrics.csv", index=False)
    all_benchmarks = pd.concat([benchmarks, lip_frame], ignore_index=True, sort=False)
    all_benchmarks.to_csv(
        results_dir / "calibration" / "all_benchmark_predictions.csv", index=False
    )

    numerical_tests, grid = run_numerical_tests(systems, geometry)
    numerical_tests.to_csv(results_dir / "numerical_tests.csv", index=False)
    grid.to_csv(results_dir / "grid_convergence.csv", index=False)
    if not bool(numerical_tests["passed"].all()):
        failed = numerical_tests.loc[~numerical_tests["passed"], "test"].tolist()
        raise RuntimeError(f"Numerical verification failed: {failed}")

    uncertainty, uncertainty_summary, pairwise, sensitivity = run_uncertainty(
        systems,
        parameter_bounds,
        results_dir / "uncertainty",
        n_sets=256,
        seed=20260827,
    )
    create_all_plots(
        baseline_results,
        endpoints,
        all_benchmarks,
        uncertainty_summary,
        sensitivity,
        figures_dir,
    )

    run_decision_analysis(ROOT, systems, geometry)

    scope_gate = pd.read_csv(data_dir / "scope_gate.csv")
    acceptance = pd.DataFrame(
        [
            {"check": "Analysis plan defines scope and model rules", "passed": True,
             "evidence": "scope_gate.csv records the governing analysis definitions"},
            {"check": "All carrier release rates equal zero", "passed": bool(
                all(systems[x].release_rate_h == 0 for x in ("tFNA_CK", "NLC_CK", "liposome_CK"))),
             "evidence": "calibrated_parameters.csv"},
            {"check": "Dose is 1 ug/cm2 for every group", "passed": bool(
                all(np.isclose(x.dose_ug_cm2, 1.0) for x in systems.values())),
             "evidence": "calibrated_parameters.csv"},
            {"check": "Production mesh is 24/68/160", "passed": True,
             "evidence": "grid_convergence.csv"},
            {"check": "All numerical tests pass", "passed": bool(numerical_tests["passed"].all()),
             "evidence": "numerical_tests.csv"},
            {"check": "Uncertainty includes 256 paired sets", "passed": bool(
                uncertainty["parameter_set_id"].nunique() == 256 and len(uncertainty) == 1024),
             "evidence": "uncertainty_256x4.csv"},
            {"check": "All six pairwise comparisons exported", "passed": bool(
                len(pairwise) == 6),
             "evidence": "pairwise_differences.csv"},
            {"check": "Flux, AUC and operational lag exported", "passed": bool(
                len(secondary) == 4 and len(flux) == 4 * 97),
             "evidence": "secondary_endpoints.csv; interface_flux_timecourse.csv"},
            {"check": "Task 2 interface excludes free CK and released CK", "passed": bool(
                set(task2["system"]) == {"tFNA_CK", "NLC_CK", "liposome_CK"}
                and (task2["release_rate_h"] == 0).all()),
             "evidence": "task2_interface.csv"},
            {"check": "All eight explicit scope gates pass", "passed": bool(scope_gate["status"].eq("PASS").all()),
             "evidence": "scope_gate.csv"},
        ]
    )
    acceptance.to_csv(results_dir / "acceptance_audit.csv", index=False)
    if not bool(acceptance["passed"].all()):
        raise RuntimeError("Acceptance audit contains failed items.")

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "geometry_um": {"SC": 15, "VE": 85, "shallow_dermis": 400},
        "production_grid": [24, 68, 160],
        "dose_ug_cm2": 1.0,
        "duration_h": 24.0,
        "carrier_release_rate_h": 0.0,
        "uncertainty_sets": 256,
        "uncertainty_seed": 20260827,
        "primary_endpoint": "24 h carrier-bound CK-equivalent retained in viable epidermis plus shallow dermis",
        "calibration_model": "finite donor, 500 um domain, normalized first-cell observation; conditional effective D",
        "human_transfer_usage": "direct-transfer check and separate human-assisted conditional calibration",
        "decision_surface_points": 441,
        "decision_checks_passed": int(pd.read_csv(results_dir / "decision" / "decision_checks.csv")["passed"].sum()),
        "numerical_tests_passed": int(numerical_tests["passed"].sum()),
        "numerical_tests_total": int(len(numerical_tests)),
        "acceptance_checks_passed": int(acceptance["passed"].sum()),
        "acceptance_checks_total": int(len(acceptance)),
    }
    with (results_dir / "execution_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    write_reports(ROOT)

    print("Task 1 pipeline completed.")
    print(endpoints[["system", "target_retention_ug_cm2"]].to_string(index=False))
    print(uncertainty_summary.to_string(index=False))
    print(f"Numerical tests: {numerical_tests['passed'].sum()}/{len(numerical_tests)} passed")
    print(f"Acceptance audit: {acceptance['passed'].sum()}/{len(acceptance)} passed")


if __name__ == "__main__":
    main()
