from __future__ import annotations

import json
from dataclasses import asdict
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar

from .model import Geometry, SystemParameters, simulate


def semi_infinite_profile(depth_um: np.ndarray, time_h: float, diffusion_cm2_h: float) -> np.ndarray:
    depth_cm = np.asarray(depth_um, dtype=float) * 1e-4
    denominator = 2.0 * sqrt(diffusion_cm2_h * time_h)
    return np.asarray([erfc(value / denominator) for value in depth_cm])


def _fit_profile(
    depth_um: np.ndarray,
    normalized_signal: np.ndarray,
    time_h: float,
) -> tuple[float, pd.DataFrame, dict[str, float]]:
    observed = np.asarray(normalized_signal, dtype=float)
    depth = np.asarray(depth_um, dtype=float)

    def residual(log10_d: np.ndarray) -> np.ndarray:
        predicted = semi_infinite_profile(depth, time_h, 10 ** log10_d[0])
        return predicted - observed

    fit = least_squares(
        residual,
        x0=np.asarray([-5.0]),
        bounds=(-9.0, -2.0),
        loss="soft_l1",
        f_scale=0.08,
    )
    diffusion = float(10 ** fit.x[0])
    predicted = semi_infinite_profile(depth, time_h, diffusion)
    metrics = regression_metrics(observed, predicted)
    frame = pd.DataFrame(
        {
            "depth_um": depth,
            "observed_normalized": observed,
            "predicted_normalized": predicted,
        }
    )
    return diffusion, frame, metrics


def regression_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    residual = predicted - observed
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((observed - np.mean(observed)) ** 2))
    return {
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "mae": float(np.mean(np.abs(residual))),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
        "mean_relative_error": float(
            np.mean(np.abs(residual) / np.maximum(np.abs(observed), 0.05))
        ),
        "n": int(len(observed)),
    }


def finite_profile(depth_um, diffusion_cm2_h, geometry=None, surface_p=0.0015):
    """Observation operator: first-cell surface proxy, linear interpolation, sink=0.

    Geometry and donor conditions are standardized scenario assumptions, not
    reconstructed experimental conditions. Only normalized shape is identified.
    """
    geometry = geometry or Geometry()
    p = SystemParameters("tFNA_CK", "normalized carrier proxy",
                         (diffusion_cm2_h,) * 3, (1.,) * 3, surface_p)
    result = simulate(p, geometry=geometry, times_h=[0., 24.], solver="BDF")
    c = result.concentration[-1]
    x = np.r_[0., result.mesh.depth_um.to_numpy(), geometry.total_um]
    y = np.r_[c[0], c, 0.] / max(c[0], 1e-30)
    return np.interp(depth_um, x, y)


def fit_finite_profile(depth, observed, geometry=None, surface_p=0.0015):
    depth, observed = np.asarray(depth), np.asarray(observed)
    fit = least_squares(
        lambda logd: finite_profile(depth, 10**logd[0], geometry, surface_p)-observed,
        [-5.], bounds=(-9., -2.), loss="soft_l1", f_scale=0.08)
    d = float(10**fit.x[0])
    predicted = finite_profile(depth, d, geometry, surface_p)
    frame = pd.DataFrame(dict(depth_um=depth, observed_normalized=observed,
                              predicted_normalized=predicted))
    return d, frame, regression_metrics(observed, predicted)


def fit_tfna_human(data_dir: Path) -> tuple[float, pd.DataFrame, dict[str, float]]:
    data = pd.read_csv(data_dir / "wiraja2019_human_th21_depth.csv")
    data = data.loc[data["depth_um"] <= 200].copy()
    return _fit_profile(
        data["depth_um"].to_numpy(),
        data["normalized_to_surface"].to_numpy(),
        24.0,
    )


def _pig_profile(data_dir: Path, system: str, max_depth_um: float = 500.0) -> pd.DataFrame:
    data = pd.read_csv(data_dir / "wiraja2019_pig_dox_depth.csv")
    data = data.loc[
        (data["system"] == system) & (data["depth_um"] <= max_depth_um)
    ].copy()
    # tDOX is the free-DOX comparator in Fig. 4, not an untreated background.
    # The carrier curves therefore use their measured fluorescence directly.
    surface = float(data.loc[data["depth_um"].idxmin(), "mean_signal"])
    data["normalized_raw_to_surface"] = data["mean_signal"] / surface
    return data


def fit_liposome_pig(data_dir: Path) -> tuple[float, pd.DataFrame, dict[str, float]]:
    data = _pig_profile(data_dir, "LIP-DOX")
    return _fit_profile(
        data["depth_um"].to_numpy(),
        data["normalized_raw_to_surface"].to_numpy(),
        24.0,
    )


def fit_tfna_pig(
    data_dir: Path,
) -> tuple[float, pd.DataFrame, dict[str, float]]:
    data = _pig_profile(data_dir, "TH-DOX")
    diffusion, frame, metrics = _fit_profile(
        data["depth_um"].to_numpy(),
        data["normalized_raw_to_surface"].to_numpy(),
        24.0,
    )
    return diffusion, frame, metrics


def validate_tfna_human(
    data_dir: Path, diffusion_cm2_h: float
) -> tuple[pd.DataFrame, dict[str, float]]:
    data = pd.read_csv(data_dir / "wiraja2019_human_th21_depth.csv")
    data = data.loc[data["depth_um"] <= 200].copy()
    observed = data["normalized_to_surface"].to_numpy(dtype=float)
    predicted = semi_infinite_profile(
        data["depth_um"].to_numpy(), 24.0, diffusion_cm2_h
    )
    frame = pd.DataFrame(
        {
            "depth_um": data["depth_um"].to_numpy(),
            "observed_normalized": observed,
            "predicted_normalized": predicted,
        }
    )
    return frame, regression_metrics(observed, predicted)


def _dermis_fraction(result, time_h: float) -> float:
    row = result.layer_mass_frame().iloc[
        int(np.argmin(np.abs(result.times_h - time_h)))
    ]
    epidermal = float(row["SC_mass_ug_cm2"] + row["VE_mass_ug_cm2"])
    dermis = float(row["dermis_mass_ug_cm2"])
    return dermis / (epidermal + dermis) if epidermal + dermis > 0 else 0.0


def fit_nlc_layer_fractions(
    geometry: Geometry,
    surface_permeability_cm_h: float = 0.0015,
) -> tuple[float, pd.DataFrame, dict[str, float]]:
    targets = {3.0: 4.0 / 62.0, 6.0: 47.0 / 150.0}

    def objective(log10_d: float) -> float:
        diffusion = 10**log10_d
        params = SystemParameters(
            system="NLC_CK",
            state_label="carrier-bound CK-equivalent",
            diffusion_cm2_h=(diffusion, diffusion, diffusion),
            partition=(1.0, 1.0, 1.0),
            surface_permeability_cm_h=surface_permeability_cm_h,
            evidence_label="PPD-NLC proxy",
        )
        result = simulate(
            params,
            geometry=geometry,
            cells_per_layer=(24, 68, 160),
            times_h=[0.0, 3.0, 6.0],
            solver="BDF",
        )
        residuals = [
            _dermis_fraction(result, time_h) - target
            for time_h, target in targets.items()
        ]
        return float(np.sum(np.square(residuals)))

    fit = minimize_scalar(objective, bounds=(-8.5, -3.0), method="bounded")
    diffusion = float(10**fit.x)
    params = SystemParameters(
        system="NLC_CK",
        state_label="carrier-bound CK-equivalent",
        diffusion_cm2_h=(diffusion, diffusion, diffusion),
        partition=(1.0, 1.0, 1.0),
        surface_permeability_cm_h=surface_permeability_cm_h,
        evidence_label="PPD-NLC proxy",
    )
    result = simulate(
        params,
        geometry=geometry,
        cells_per_layer=(24, 68, 160),
        times_h=[0.0, 3.0, 6.0],
    )
    observed = np.asarray([targets[3.0], targets[6.0]])
    predicted = np.asarray(
        [_dermis_fraction(result, 3.0), _dermis_fraction(result, 6.0)]
    )
    frame = pd.DataFrame(
        {
            "time_h": [3.0, 6.0],
            "observed_normalized": observed,
            "predicted_normalized": predicted,
        }
    )
    return diffusion, frame, regression_metrics(observed, predicted)


def calibrated_systems(
    data_dir: str | Path,
    output_dir: str | Path | None = None,
    geometry: Geometry | None = None,
) -> tuple[
    dict[str, SystemParameters],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    data_dir = Path(data_dir)
    geometry = geometry or Geometry()
    carrier_surface_p = 0.0015

    profiles = [_pig_profile(data_dir, name) for name in ("TH-DOX", "LIP-DOX")]
    tfna_d, tfna_fit, tfna_fit_metrics = fit_finite_profile(
        profiles[0].depth_um, profiles[0].normalized_raw_to_surface, geometry)
    lip_d, lip_fit, lip_fit_metrics = fit_finite_profile(
        profiles[1].depth_um, profiles[1].normalized_raw_to_surface, geometry)
    nlc_d, nlc_fit, nlc_metrics = fit_nlc_layer_fractions(
        geometry, surface_permeability_cm_h=carrier_surface_p
    )
    human = pd.read_csv(data_dir / "wiraja2019_human_th21_depth.csv")
    tfna_human = pd.DataFrame(dict(depth_um=human.depth_um,
        observed_normalized=human.normalized_to_surface,
        predicted_normalized=finite_profile(human.depth_um, tfna_d, geometry)))
    tfna_human_metrics = regression_metrics(tfna_human.observed_normalized,
                                           tfna_human.predicted_normalized)

    # Potts-Guy baseline: log10(Kp[cm/h]) = -2.72 + 0.71 logP - 0.0061 MW.
    ck_mw = 622.9
    ck_logp = 5.6
    kp_cm_h = 10 ** (-2.72 + 0.71 * ck_logp - 0.0061 * ck_mw)
    k_sc = 25.0
    d_sc = kp_cm_h * geometry.sc_um * 1e-4 / k_sc

    systems = {
        "free_CK": SystemParameters(
            system="free_CK",
            state_label="free CK",
            diffusion_cm2_h=(d_sc, 5.0e-6, 1.0e-5),
            partition=(k_sc, 2.0, 1.5),
            surface_permeability_cm_h=0.10,
            evidence_label="Potts-Guy free-CK baseline",
        ),
        "tFNA_CK": SystemParameters(
            system="tFNA_CK",
            state_label="intact tFNA-bound CK-equivalent",
            diffusion_cm2_h=(tfna_d, tfna_d, tfna_d),
            partition=(1.0, 1.0, 1.0),
            surface_permeability_cm_h=carrier_surface_p,
            evidence_label="Wiraja paired porcine TH-DOX depth calibration",
        ),
        "NLC_CK": SystemParameters(
            system="NLC_CK",
            state_label="intact NLC-bound CK-equivalent",
            diffusion_cm2_h=(nlc_d, nlc_d, nlc_d),
            partition=(1.0, 1.0, 1.0),
            surface_permeability_cm_h=carrier_surface_p,
            evidence_label="Kim PPD-NLC layer-fraction proxy calibration",
        ),
        "liposome_CK": SystemParameters(
            system="liposome_CK",
            state_label="intact liposome-bound CK-equivalent",
            diffusion_cm2_h=(lip_d, lip_d, lip_d),
            partition=(1.0, 1.0, 1.0),
            surface_permeability_cm_h=carrier_surface_p,
            evidence_label="Wiraja porcine LIP-DOX normalized-depth proxy calibration",
        ),
    }

    fit_rows: list[dict[str, float | str]] = []
    for label, metrics, usage in (
        ("tFNA_pig_TH_DOX_depth", tfna_fit_metrics, "paired_proxy_calibration"),
        ("liposome_pig_LIP_DOX_depth", lip_fit_metrics, "paired_proxy_calibration"),
        ("tFNA_human_TH21_depth", tfna_human_metrics, "cross_condition_benchmark"),
        ("NLC_human_layer_fraction_3h_6h", nlc_metrics, "proxy_calibration"),
    ):
        fit_rows.append({"benchmark": label, "usage": usage, **metrics})
    metrics_frame = pd.DataFrame(fit_rows)

    benchmark_rows: list[pd.DataFrame] = []
    for name, usage, frame in (
        ("tFNA_pig_TH_DOX_depth", "paired_proxy_calibration", tfna_fit),
        ("liposome_pig_LIP_DOX_depth", "paired_proxy_calibration", lip_fit),
        ("tFNA_human_TH21_depth", "cross_condition_benchmark", tfna_human),
    ):
        block = frame.copy()
        block.insert(0, "benchmark", name)
        block.insert(1, "usage", usage)
        benchmark_rows.append(block)
    nlc_block = nlc_fit.copy()
    nlc_block.insert(0, "benchmark", "NLC_human_layer_fraction_3h_6h")
    nlc_block.insert(1, "usage", "proxy_calibration")
    nlc_block["depth_um"] = np.nan
    benchmark_rows.append(nlc_block)
    benchmark_frame = pd.concat(benchmark_rows, ignore_index=True)

    bounds_frame = pd.DataFrame(
        [
            {
                "system": "free_CK",
                "parameter": "D_multiplier",
                "lower_bound": 0.5,
                "upper_bound": 2.0,
                "scale": "log_uniform",
                "basis": "Potts-Guy engineering uncertainty",
            },
            {
                "system": "tFNA_CK",
                "parameter": "D_cm2_h",
                "lower_bound": tfna_d * 0.5,
                "upper_bound": tfna_d * 2.0,
                "scale": "log_uniform",
                "basis": "Paired porcine TH-DOX baseline x0.5 to x2",
            },
            {
                "system": "NLC_CK",
                "parameter": "D_cm2_h",
                "lower_bound": nlc_d * 0.25,
                "upper_bound": nlc_d * 4.0,
                "scale": "log_uniform",
                "basis": "Two-time-point digitized PPD proxy and state mismatch",
            },
            {
                "system": "liposome_CK",
                "parameter": "D_cm2_h",
                "lower_bound": lip_d * 0.5,
                "upper_bound": lip_d * 2.0,
                "scale": "log_uniform",
                "basis": "Paired porcine LIP-DOX profile uncertainty",
            },
        ]
    )

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        parameter_rows = []
        for system, params in systems.items():
            parameter_rows.append(
                {
                    "system": system,
                    "state_label": params.state_label,
                    "D_SC_cm2_h": params.diffusion_cm2_h[0],
                    "D_VE_cm2_h": params.diffusion_cm2_h[1],
                    "D_dermis_cm2_h": params.diffusion_cm2_h[2],
                    "K_SC": params.partition[0],
                    "K_VE": params.partition[1],
                    "K_dermis": params.partition[2],
                    "surface_permeability_cm_h": params.surface_permeability_cm_h,
                    "release_rate_h": params.release_rate_h,
                    "dose_ug_cm2": params.dose_ug_cm2,
                    "evidence_label": params.evidence_label,
                }
            )
        pd.DataFrame(parameter_rows).to_csv(
            output_dir / "calibrated_parameters.csv", index=False
        )
        benchmark_frame.to_csv(output_dir / "benchmark_predictions.csv", index=False)
        metrics_frame.to_csv(output_dir / "benchmark_metrics.csv", index=False)
        bounds_frame.to_csv(output_dir / "parameter_uncertainty_bounds.csv", index=False)
        corrected_profiles = pd.concat(
            [
                _pig_profile(data_dir, "TH-DOX").assign(profile_usage="tFNA_proxy"),
                _pig_profile(data_dir, "LIP-DOX").assign(profile_usage="liposome_proxy"),
            ],
            ignore_index=True,
        )
        corrected_profiles.to_csv(
            output_dir / "wiraja_pig_dox_profiles_for_calibration.csv", index=False
        )
        with (output_dir / "calibrated_parameters.json").open("w", encoding="utf-8") as handle:
            json.dump(
                {system: asdict(params) for system, params in systems.items()},
                handle,
                ensure_ascii=False,
                indent=2,
            )

    return systems, benchmark_frame, metrics_frame, bounds_frame
