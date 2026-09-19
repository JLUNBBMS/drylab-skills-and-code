from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from math import pi
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import expm_multiply
from scipy.stats import qmc, spearmanr

from .calibration import regression_metrics
from .model import Geometry, SimulationResult, SystemParameters, export_result, simulate


SYSTEM_ORDER = ["free_CK", "tFNA_CK", "NLC_CK", "liposome_CK"]


def run_baseline(
    systems: dict[str, SystemParameters],
    geometry: Geometry,
    output_dir: str | Path,
) -> tuple[dict[str, SimulationResult], pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    times = np.linspace(0.0, 24.0, 97)
    results: dict[str, SimulationResult] = {}
    endpoints: list[dict[str, float | str]] = []
    all_layer_frames: list[pd.DataFrame] = []
    for system in SYSTEM_ORDER:
        result = simulate(
            systems[system],
            geometry=geometry,
            cells_per_layer=(24, 68, 160),
            times_h=times,
            solver="expm",
        )
        results[system] = result
        export_result(result, output_dir / "by_system")
        endpoints.append(result.endpoint(24.0))
        all_layer_frames.append(result.layer_mass_frame())
    endpoint_frame = pd.DataFrame(endpoints)
    endpoint_frame.to_csv(output_dir / "baseline_24h_endpoints.csv", index=False)
    pd.concat(all_layer_frames, ignore_index=True).to_csv(
        output_dir / "baseline_layer_mass_timecourse.csv", index=False
    )
    return results, endpoint_frame


def export_task2_interface(
    results: dict[str, SimulationResult], output_path: str | Path
) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for system in ("tFNA_CK", "NLC_CK", "liposome_CK"):
        result = results[system]
        layer_mass = result.layer_mass_frame()
        layer_volumes = (
            result.mesh.groupby("skin_layer", sort=False)["volume_cm3"].sum().to_dict()
        )
        for _, row in layer_mass.iterrows():
            for layer, mass_column in (
                ("SC", "SC_mass_ug_cm2"),
                ("VE", "VE_mass_ug_cm2"),
                ("dermis", "dermis_mass_ug_cm2"),
            ):
                mass = float(row[mass_column])
                rows.append(
                    {
                        "system": system,
                        "time_h": float(row["time_h"]),
                        "skin_layer": layer,
                        "carrier_bound_ck_concentration_ug_cm3": mass
                        / float(layer_volumes[layer]),
                        "carrier_bound_ck_mass_ug_cm2": mass,
                        "cumulative_net_into_VE_ug_cm2": float(
                            row["cumulative_net_into_VE_ug_cm2"]
                        ),
                        "cumulative_net_into_dermis_ug_cm2": float(
                            row["cumulative_net_into_dermis_ug_cm2"]
                        ),
                        "parameter_set_id": "baseline",
                        "release_rate_h": 0.0,
                    }
                )
    frame = pd.DataFrame(rows)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def export_secondary_endpoints(
    results: dict[str, SimulationResult], output_dir: str | Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, float | str]] = []
    flux_frames: list[pd.DataFrame] = []
    for system in SYSTEM_ORDER:
        result = results[system]
        times = result.times_h
        layer_mass = result.layer_mass_frame()
        into_ve = layer_mass["cumulative_net_into_VE_ug_cm2"].to_numpy(dtype=float)
        into_dermis = layer_mass[
            "cumulative_net_into_dermis_ug_cm2"
        ].to_numpy(dtype=float)
        flux_ve = np.gradient(into_ve, times, edge_order=2)
        flux_dermis = np.gradient(into_dermis, times, edge_order=2)
        flux_frames.append(
            pd.DataFrame(
                {
                    "system": system,
                    "time_h": times,
                    "net_flux_into_VE_ug_cm2_h": flux_ve,
                    "net_flux_into_dermis_ug_cm2_h": flux_dermis,
                }
            )
        )

        mean_concentrations: dict[str, np.ndarray] = {}
        for layer in ("SC", "VE", "dermis"):
            mask = result.mesh["skin_layer"].eq(layer).to_numpy()
            volume = float(result.mesh.loc[mask, "volume_cm3"].sum())
            mean_concentrations[layer] = result.cell_mass[:, mask].sum(axis=1) / volume

        final_dermis = float(into_dermis[-1])
        lag_threshold = 0.10 * final_dermis
        lag_indices = np.flatnonzero(into_dermis >= lag_threshold)
        lag_h = float(times[lag_indices[0]]) if len(lag_indices) else float("nan")
        summary_rows.append(
            {
                "system": system,
                "SC_concentration_AUC_ug_h_cm3": float(
                    np.trapezoid(mean_concentrations["SC"], times)
                ),
                "VE_concentration_AUC_ug_h_cm3": float(
                    np.trapezoid(mean_concentrations["VE"], times)
                ),
                "dermis_concentration_AUC_ug_h_cm3": float(
                    np.trapezoid(mean_concentrations["dermis"], times)
                ),
                "max_net_flux_into_VE_ug_cm2_h": float(np.max(flux_ve)),
                "max_net_flux_into_dermis_ug_cm2_h": float(np.max(flux_dermis)),
                "operational_lag_h_to_10pct_24h_dermis_entry": lag_h,
                "lag_definition": "first time reaching 10% of the system's 24 h net dermis entry",
            }
        )
    summary = pd.DataFrame(summary_rows)
    flux = pd.concat(flux_frames, ignore_index=True)
    summary.to_csv(output_dir / "secondary_endpoints.csv", index=False)
    flux.to_csv(output_dir / "interface_flux_timecourse.csv", index=False)
    return summary, flux


def validate_liposome_timecourse(
    liposome_parameters: SystemParameters,
    geometry: Geometry,
    data_dir: str | Path,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    observed = pd.read_csv(Path(data_dir) / "jin2022_ginsenoside_liposome_timecourse.csv")
    observed = observed.loc[observed["system"] == "GSL-7"].copy()
    times = np.r_[0.0, observed["time_h"].to_numpy(dtype=float)]
    result = simulate(
        liposome_parameters,
        geometry=geometry,
        cells_per_layer=(24, 68, 160),
        times_h=times,
    )
    entered = liposome_parameters.dose_ug_cm2 - result.reservoir_mass[1:]
    predicted_normalized = entered / entered[-1]
    observed_normalized = (
        observed["total_skin_transmission_pct"].to_numpy(dtype=float)
        / float(observed["total_skin_transmission_pct"].iloc[-1])
    )
    frame = pd.DataFrame(
        {
            "benchmark": "liposome_GSL7_rat_skin_timecourse",
            "usage": "held_out_proxy_validation",
            "time_h": observed["time_h"].to_numpy(dtype=float),
            "observed_normalized": observed_normalized,
            "predicted_normalized": predicted_normalized,
        }
    )
    return frame, regression_metrics(observed_normalized, predicted_normalized)


def single_layer_analytic_test() -> dict[str, float | str | bool]:
    length_cm = 0.05
    diffusion = 1.0e-5
    count = 160
    dx = length_cm / count
    time_h = 50.0
    x = (np.arange(count) + 0.5) * dx

    matrix = lil_matrix((count + 1, count + 1), dtype=float)
    constant = count
    rate = diffusion / dx**2
    for i in range(count):
        if i > 0:
            matrix[i, i - 1] += rate
            matrix[i, i] -= rate
        else:
            matrix[i, i] -= 2.0 * rate
            matrix[i, constant] += 2.0 * rate
        if i < count - 1:
            matrix[i, i + 1] += rate
            matrix[i, i] -= rate
        else:
            matrix[i, i] -= 2.0 * rate
    state0 = np.zeros(count + 1)
    state0[constant] = 1.0
    numeric = expm_multiply(matrix.tocsc() * time_h, state0)[:count]

    analytic = 1.0 - x / length_cm
    for n in range(1, 401):
        analytic -= (
            2.0
            / (n * pi)
            * np.sin(n * pi * x / length_cm)
            * np.exp(-(n * pi) ** 2 * diffusion * time_h / length_cm**2)
        )
    rmse = float(np.sqrt(np.mean((numeric - analytic) ** 2)))
    return {
        "test": "single_layer_dirichlet_analytic",
        "metric": "RMSE",
        "value": rmse,
        "threshold": 0.005,
        "passed": rmse < 0.005,
        "notes": "Cell-centered finite-volume solution vs 400-term slab series",
    }


def run_numerical_tests(
    systems: dict[str, SystemParameters], geometry: Geometry
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, float | str | bool]] = [single_layer_analytic_test()]
    grid_rows: list[dict[str, float | str]] = []
    grid_specs = {
        "coarse": (12, 34, 80),
        "production": (24, 68, 160),
        "fine": (36, 102, 240),
    }
    for system in SYSTEM_ORDER:
        parameter = systems[system]
        production = simulate(
            parameter,
            geometry=geometry,
            cells_per_layer=grid_specs["production"],
            times_h=[0.0, 24.0],
        )
        mass_error = float(
            np.max(np.abs(production.layer_mass_frame()["mass_balance_error"]))
        )
        min_state = float(np.min(production.states))
        rows.append(
            {
                "test": f"mass_conservation_{system}",
                "metric": "max_abs_error_ug_cm2",
                "value": mass_error,
                "threshold": 1e-9,
                "passed": mass_error < 1e-9,
                "notes": "Reservoir + three skin layers + sink",
            }
        )
        rows.append(
            {
                "test": f"nonnegativity_{system}",
                "metric": "minimum_state_ug",
                "value": min_state,
                "threshold": -1e-12,
                "passed": min_state >= -1e-12,
                "notes": "Tiny values below 1e-14 are rounded to zero",
            }
        )

        endpoint_by_grid: dict[str, float] = {}
        for grid_name, grid in grid_specs.items():
            result = simulate(
                parameter,
                geometry=geometry,
                cells_per_layer=grid,
                times_h=[0.0, 24.0],
            )
            value = float(result.endpoint(24.0)["target_retention_ug_cm2"])
            endpoint_by_grid[grid_name] = value
            grid_rows.append(
                {
                    "system": system,
                    "grid": grid_name,
                    "SC_cells": grid[0],
                    "VE_cells": grid[1],
                    "dermis_cells": grid[2],
                    "target_retention_ug_cm2": value,
                }
            )
        relative = abs(
            endpoint_by_grid["production"] - endpoint_by_grid["fine"]
        ) / max(abs(endpoint_by_grid["fine"]), 1e-12)
        rows.append(
            {
                "test": f"grid_convergence_{system}",
                "metric": "production_vs_fine_relative_error",
                "value": relative,
                "threshold": 0.02,
                "passed": relative < 0.02,
                "notes": "Primary 24 h endpoint",
            }
        )

        bdf = simulate(
            parameter,
            geometry=geometry,
            cells_per_layer=grid_specs["production"],
            times_h=[0.0, 24.0],
            solver="BDF",
        )
        expm_endpoint = production.states[-1]
        bdf_endpoint = bdf.states[-1]
        solver_error = float(
            np.linalg.norm(expm_endpoint - bdf_endpoint, ord=1)
            / max(np.linalg.norm(expm_endpoint, ord=1), 1e-12)
        )
        rows.append(
            {
                "test": f"solver_crosscheck_{system}",
                "metric": "L1_relative_error",
                "value": solver_error,
                "threshold": 1e-6,
                "passed": solver_error < 1e-6,
                "notes": "Sparse matrix exponential vs BDF",
            }
        )

    # Potts-Guy formula is an independent baseline calculation, not a fitted output.
    mw = 622.9
    logp = 5.6
    kp = 10 ** (-2.72 + 0.71 * logp - 0.0061 * mw)
    rows.append(
        {
            "test": "Potts_Guy_free_CK_baseline",
            "metric": "Kp_cm_h",
            "value": kp,
            "threshold": np.nan,
            "passed": np.isclose(kp, 0.0028596310236070935, rtol=1e-10),
            "notes": "MW 622.9; XLogP 5.6; equation in Potts and Guy (1992)",
        }
    )
    return pd.DataFrame(rows), pd.DataFrame(grid_rows)


def _log_uniform(lower: float, upper: float, unit_value: float) -> float:
    return float(np.exp(np.log(lower) + unit_value * (np.log(upper) - np.log(lower))))


def run_uncertainty(
    systems: dict[str, SystemParameters],
    parameter_bounds: pd.DataFrame,
    output_dir: str | Path,
    n_sets: int = 256,
    seed: int = 20260827,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    variable_names = [
        "SC_thickness_um",
        "VE_thickness_um",
        "dermis_thickness_um",
        "barrier_factor",
        "CK_logP",
    ]
    for system in SYSTEM_ORDER:
        variable_names.extend(
            [f"{system}_D_draw", f"{system}_K_mult", f"{system}_surface_P_cm_h"]
        )
    sample = qmc.LatinHypercube(d=len(variable_names), seed=seed).random(n_sets)
    uncertainty_rows: list[dict[str, float | int | str]] = []
    input_rows: list[dict[str, float | int]] = []

    for set_index, unit in enumerate(sample):
        cursor = 0
        sc_um = 10.0 + 10.0 * unit[cursor]
        cursor += 1
        ve_um = 60.0 + 60.0 * unit[cursor]
        cursor += 1
        dermis_um = 300.0 + 200.0 * unit[cursor]
        cursor += 1
        barrier_factor = _log_uniform(0.5, 1.5, unit[cursor])
        cursor += 1
        ck_logp = 5.2 + 0.8 * unit[cursor]
        cursor += 1
        geometry = Geometry(sc_um=sc_um, ve_um=ve_um, dermis_um=dermis_um)
        input_record: dict[str, float | int] = {
            "parameter_set_id": set_index,
            "SC_thickness_um": sc_um,
            "VE_thickness_um": ve_um,
            "dermis_thickness_um": dermis_um,
            "barrier_factor": barrier_factor,
            "CK_logP": ck_logp,
        }

        system_draws: dict[str, tuple[float, float, float]] = {}
        for system in SYSTEM_ORDER:
            if system == "free_CK":
                d_draw = _log_uniform(0.5, 2.0, unit[cursor])
            else:
                bound = parameter_bounds.loc[
                    (parameter_bounds["system"] == system)
                    & (parameter_bounds["parameter"] == "D_cm2_h")
                ].iloc[0]
                d_draw = _log_uniform(
                    float(bound["lower_bound"]),
                    float(bound["upper_bound"]),
                    unit[cursor],
                )
            cursor += 1
            k_mult = _log_uniform(0.3, 3.0, unit[cursor])
            cursor += 1
            if system == "free_CK":
                surface_p = _log_uniform(0.03, 0.30, unit[cursor])
            else:
                surface_p = _log_uniform(1.0e-4, 1.0e-2, unit[cursor])
            cursor += 1
            input_record[f"{system}_D_draw"] = d_draw
            input_record[f"{system}_K_mult"] = k_mult
            input_record[f"{system}_surface_P_cm_h"] = surface_p
            system_draws[system] = (d_draw, k_mult, surface_p)

        for system in SYSTEM_ORDER:
            base = systems[system]
            d_draw, k_mult, surface_p = system_draws[system]

            if system == "free_CK":
                mw = 622.9
                kp = 10 ** (-2.72 + 0.71 * ck_logp - 0.0061 * mw)
                k_sc = base.partition[0] * k_mult
                d_sc = kp * sc_um * 1e-4 / k_sc
                diffusion = (
                    d_sc * barrier_factor * d_draw,
                    base.diffusion_cm2_h[1] * d_draw,
                    base.diffusion_cm2_h[2] * d_draw,
                )
                partition = tuple(value * k_mult for value in base.partition)
            else:
                # Shared skin-barrier variability acts on the stratum corneum only.
                diffusion = (
                    d_draw * barrier_factor,
                    d_draw,
                    d_draw,
                )
                partition = tuple(value * k_mult for value in base.partition)
            parameters = replace(
                base,
                diffusion_cm2_h=diffusion,
                partition=partition,
                surface_permeability_cm_h=surface_p,
            )
            result = simulate(
                parameters,
                geometry=geometry,
                cells_per_layer=(24, 68, 160),
                times_h=[0.0, 24.0],
                # The BDF endpoint solver is ~20--250x faster for the stiff
                # carrier cases and was cross-checked against expm above.
                solver="BDF",
            )
            endpoint = result.endpoint(24.0)
            uncertainty_rows.append(
                {
                    "parameter_set_id": set_index,
                    **input_record,
                    **endpoint,
                }
            )
        input_rows.append(input_record)

    uncertainty = pd.DataFrame(uncertainty_rows)
    inputs = pd.DataFrame(input_rows)
    uncertainty.to_csv(output_dir / f"uncertainty_{n_sets}x4.csv", index=False)
    inputs.to_csv(output_dir / f"uncertainty_parameter_sets_{n_sets}.csv", index=False)

    summaries: list[dict[str, float | str]] = []
    for system in SYSTEM_ORDER:
        values = uncertainty.loc[
            uncertainty["system"] == system, "target_retention_ug_cm2"
        ].to_numpy(dtype=float)
        summaries.append(
            {
                "system": system,
                "median_target_retention_ug_cm2": float(np.median(values)),
                "lower_95_ug_cm2": float(np.quantile(values, 0.025)),
                "upper_95_ug_cm2": float(np.quantile(values, 0.975)),
                "mean_ug_cm2": float(np.mean(values)),
                "scenario_count": int(n_sets),
            }
        )
    summary = pd.DataFrame(summaries)

    pivot = uncertainty.pivot(
        index="parameter_set_id", columns="system", values="target_retention_ug_cm2"
    )
    winner = pivot.idxmax(axis=1)
    win_probabilities = winner.value_counts(normalize=True).to_dict()
    summary["probability_best"] = summary["system"].map(win_probabilities).fillna(0.0)
    summary.to_csv(output_dir / "uncertainty_summary.csv", index=False)

    pairwise_rows: list[dict[str, float | str | bool]] = []
    for first, second in combinations(SYSTEM_ORDER, 2):
        diff = pivot[first] - pivot[second]
        lower = float(np.quantile(diff, 0.025))
        upper = float(np.quantile(diff, 0.975))
        pairwise_rows.append(
            {
                "first_system": first,
                "second_system": second,
                "median_difference_ug_cm2": float(np.median(diff)),
                "lower_95_ug_cm2": lower,
                "upper_95_ug_cm2": upper,
                "probability_first_greater": float(np.mean(diff > 0)),
                "interval_excludes_zero": bool(lower > 0 or upper < 0),
            }
        )
    pairwise = pd.DataFrame(pairwise_rows)
    pairwise.to_csv(output_dir / "pairwise_differences.csv", index=False)

    sensitivity_rows: list[dict[str, float | str]] = []
    for system in SYSTEM_ORDER:
        system_rows = uncertainty.loc[uncertainty["system"] == system].copy()
        outcome = system_rows["target_retention_ug_cm2"].to_numpy(dtype=float)
        candidate_variables = [
            "SC_thickness_um",
            "VE_thickness_um",
            "dermis_thickness_um",
            "barrier_factor",
            "CK_logP",
            f"{system}_D_draw",
            f"{system}_K_mult",
            f"{system}_surface_P_cm_h",
        ]
        for variable in candidate_variables:
            if variable == "CK_logP" and system != "free_CK":
                continue
            rho, p_value = spearmanr(system_rows[variable], outcome)
            sensitivity_rows.append(
                {
                    "system": system,
                    "parameter": variable,
                    "spearman_rho": float(rho),
                    "abs_spearman_rho": float(abs(rho)),
                    "p_value": float(p_value),
                }
            )
    sensitivity = pd.DataFrame(sensitivity_rows).sort_values(
        ["system", "abs_spearman_rho"], ascending=[True, False]
    )
    sensitivity.to_csv(output_dir / "sensitivity_spearman.csv", index=False)
    return uncertainty, summary, pairwise, sensitivity
