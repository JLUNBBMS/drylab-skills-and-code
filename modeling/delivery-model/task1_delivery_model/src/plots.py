from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".matplotlib")
)
import matplotlib as mpl
mpl.use("Agg", force=True)
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

from .analysis import SYSTEM_ORDER
from .model import SimulationResult


COLORS = {
    "free_CK": "#5d5d2a",
    "tFNA_CK": "#7e0909",
    "NLC_CK": "#f9a48b",
    "liposome_CK": "#DBA997",
}
LABELS = {
    "free_CK": "Free CK",
    "tFNA_CK": "tFNA-bound CK-eq. state",
    "NLC_CK": "NLC-bound CK-eq. state",
    "liposome_CK": "Liposome-bound CK-eq. state",
}
PALETTE = ["#fffaf5", "#C7C3AC", "#f9a48b", "#DBA997", "#7e0909"]


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
        }
    )


def _save(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{stem}.png", dpi=320, bbox_inches="tight")
    fig.savefig(output_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def plot_workflow(output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 3.3))
    ax.axis("off")
    boxes = [
        ("Scope gate", "Intact carrier only\nrelease rate = 0"),
        ("Evidence map", "Direct / proxy /\nfeasibility separated"),
        ("Calibration", "Finite-model shape fit\nNLC 3 h + 6 h\nHuman transfer scenarios"),
        ("Transport model", "Finite donor\nSC / VE / dermis\nConservative FV"),
        ("Verification", "Analytic solution\nMass + grid + solver\ncross-checks"),
        ("Decision", "VE + dermis retention\nTransfer scenarios\nDecision boundaries"),
    ]
    xs = np.linspace(0.02, 0.83, len(boxes))
    for i, ((title, body), x) in enumerate(zip(boxes, xs)):
        patch = FancyBboxPatch(
            (x, 0.28), 0.145, 0.48,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.4,
            edgecolor="#7e0909" if i in (0, 5) else "#5d5d2a",
            facecolor="#fffaf5" if i % 2 == 0 else "#f7f2ea",
            transform=ax.transAxes,
        )
        ax.add_patch(patch)
        ax.text(x + 0.0725, 0.64, title, ha="center", va="center",
                weight="bold", color="#7e0909", transform=ax.transAxes)
        ax.text(x + 0.0725, 0.44, body, ha="center", va="center",
                fontsize=8, linespacing=1.3, transform=ax.transAxes)
        if i < len(boxes) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.006, 0.52), xytext=(x + 0.151, 0.52),
                        xycoords=ax.transAxes,
                        arrowprops=dict(arrowstyle="->", color="#DBA997", lw=2))
    ax.text(0.5, 0.92, "Task 1 evidence-to-decision workflow", ha="center",
            va="center", fontsize=14, weight="bold", color="#5d5d2a",
            transform=ax.transAxes)
    ax.text(0.5, 0.09,
            "Readout gate: total cargo signals remain proxies for the carrier-bound transport state",
            ha="center", va="center", color="#7e0909", transform=ax.transAxes)
    _save(fig, output_dir, "fig01_workflow")


def plot_concentration_heatmaps(results: dict[str, SimulationResult], output_dir: Path) -> None:
    cmap = LinearSegmentedColormap.from_list("project", PALETTE)
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.4), sharex=True, sharey=True)
    arrays = []
    for system in SYSTEM_ORDER:
        arrays.append(np.log10(results[system].concentration.T + 1e-6))
    vmin = min(float(a.min()) for a in arrays)
    vmax = max(float(a.max()) for a in arrays)
    for ax, system, values in zip(axes.flat, SYSTEM_ORDER, arrays):
        result = results[system]
        image = ax.pcolormesh(result.times_h, result.mesh["depth_um"], values,
                              cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        ax.axhline(result.geometry.sc_um, color="white", lw=1.2, ls="--")
        ax.axhline(result.geometry.sc_um + result.geometry.ve_um,
                   color="white", lw=1.2, ls="--")
        ax.set_title(LABELS[system], color=COLORS[system], weight="bold")
        ax.invert_yaxis()
        ax.text(23.5, result.geometry.sc_um / 2, "SC", ha="right", va="center",
                fontsize=7, color="black")
        ax.text(23.5, result.geometry.sc_um + result.geometry.ve_um / 2, "VE",
                ha="right", va="center", fontsize=7, color="white")
        ax.text(23.5, result.geometry.sc_um + result.geometry.ve_um + 25, "Dermis",
                ha="right", va="center", fontsize=7, color="white")
    axes[1, 0].set_xlabel("Time (h)")
    axes[1, 1].set_xlabel("Time (h)")
    axes[0, 0].set_ylabel("Depth (µm)")
    axes[1, 0].set_ylabel("Depth (µm)")
    cbar = fig.colorbar(image, ax=axes, shrink=0.82, pad=0.025)
    cbar.set_label("log10 concentration (µg cm^-3 + 10^-6)")
    fig.suptitle("Depth–time concentration fields of the transport states", y=0.99,
                 fontsize=13, weight="bold", color="#5d5d2a")
    fig.text(0.5, 0.01, "Carrier panels are hypothetical bound CK-equivalent states constrained by proxy readouts.",
             ha="center", color="#7e0909")
    _save(fig, output_dir, "fig02_depth_time_heatmaps")


def plot_layer_concentrations(results: dict[str, SimulationResult], output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), sharex=True)
    for ax, layer in zip(axes, ("VE", "dermis")):
        for system in SYSTEM_ORDER:
            result = results[system]
            mask = result.mesh["skin_layer"].eq(layer).to_numpy()
            volume = float(result.mesh.loc[mask, "volume_cm3"].sum())
            mean_c = result.cell_mass[:, mask].sum(axis=1) / volume
            ax.plot(result.times_h, mean_c, color=COLORS[system], lw=2,
                    label=LABELS[system])
        ax.set_title(f"Mean {layer} concentration", weight="bold")
        ax.set_xlabel("Time (h)")
        ax.set_ylabel("Concentration (µg cm^-3)")
        ax.grid(axis="y", color="#C7C3AC", alpha=0.45, lw=0.7)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.06))
    fig.suptitle("Layer-average concentrations", y=1.15, fontsize=13,
                 weight="bold", color="#5d5d2a")
    fig.tight_layout()
    _save(fig, output_dir, "fig03_layer_average_concentration")


def plot_mass_and_cumulative(results: dict[str, SimulationResult], output_dir: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), sharex=True, sharey=True)
    layer_styles = {"SC_mass_ug_cm2": "-", "VE_mass_ug_cm2": "--",
                    "dermis_mass_ug_cm2": ":"}
    for ax, system in zip(axes.flat, SYSTEM_ORDER):
        frame = results[system].layer_mass_frame()
        for column, style in layer_styles.items():
            ax.plot(frame["time_h"], frame[column], ls=style, lw=2,
                    color=COLORS[system], label=column.split("_")[0])
        ax.plot(frame["time_h"], frame["sink_mass_ug_cm2"], ls="-.", lw=1.6,
                color=COLORS[system], label="Sink")
        ax.set_title(LABELS[system], color=COLORS[system], weight="bold")
        ax.set_xlabel("Time (h)")
        ax.set_ylabel("Mass (µg cm^-2)")
        ax.grid(axis="y", color="#C7C3AC", alpha=0.4, lw=0.7)
    axes[0, 0].set_ylim(bottom=0)
    axes[0, 0].legend(ncol=2, fontsize=8)
    fig.suptitle("Mass retained in each skin layer", fontsize=13, weight="bold",
                 color="#5d5d2a")
    fig.tight_layout()
    _save(fig, output_dir, "fig04_layer_mass_timecourse")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), sharex=True)
    for ax, endpoint in zip(axes, ("cumulative_net_into_VE_ug_cm2",
                                   "cumulative_net_into_dermis_ug_cm2")):
        for system in SYSTEM_ORDER:
            frame = results[system].layer_mass_frame()
            ax.plot(frame["time_h"], frame[endpoint], color=COLORS[system], lw=2,
                    label=LABELS[system])
        label = "viable epidermis" if "VE" in endpoint else "shallow dermis"
        ax.set_title(f"Cumulative net entry into {label}", weight="bold")
        ax.set_xlabel("Time (h)")
        ax.set_ylabel("CK-equivalent (µg cm^-2)")
        ax.grid(axis="y", color="#C7C3AC", alpha=0.45, lw=0.7)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.07))
    fig.tight_layout()
    _save(fig, output_dir, "fig05_cumulative_entry")


def plot_primary_endpoint(endpoint_frame: pd.DataFrame, output_dir: Path) -> None:
    ordered = endpoint_frame.set_index("system").loc[SYSTEM_ORDER].reset_index()
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    bars = ax.bar(np.arange(4), ordered["target_retention_ug_cm2"],
                  color=[COLORS[x] for x in SYSTEM_ORDER], width=0.68)
    ax.set_xticks(np.arange(4), [LABELS[x].replace("Intact ", "") for x in SYSTEM_ORDER],
                  rotation=10, ha="right")
    ax.set_ylabel("24 h CK-equivalent retained\nin VE + shallow dermis (µg cm^-2)")
    ax.set_title("Primary endpoint: baseline point estimates", fontsize=13,
                 weight="bold", color="#5d5d2a")
    ax.grid(axis="y", color="#C7C3AC", alpha=0.5, lw=0.7)
    for bar, value in zip(bars, ordered["target_retention_ug_cm2"]):
        ax.text(bar.get_x() + bar.get_width()/2, value + 0.012, f"{value:.3f}",
                ha="center", va="bottom", weight="bold")
    ax.text(0.5, -0.28,
            "Point estimates use proxy-calibrated transport states; evidence intervals govern interpretation.",
            transform=ax.transAxes, ha="center", color="#7e0909")
    _save(fig, output_dir, "fig06_primary_endpoint")


def plot_benchmarks(benchmarks: pd.DataFrame, output_dir: Path) -> None:
    names = list(benchmarks["benchmark"].drop_duplicates())
    ncols = 2
    nrows = int(np.ceil(len(names) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(9.5, 3.5 * nrows), squeeze=False)
    flat_axes = axes.flat
    for ax, name in zip(flat_axes, names):
        block = benchmarks.loc[benchmarks["benchmark"].eq(name)].dropna(
            subset=["observed_normalized", "predicted_normalized"]
        )
        if "depth_um" in block and block["depth_um"].notna().any():
            x = block["depth_um"]
            xlabel = "Depth (µm)"
        elif "time_h" in block and block["time_h"].notna().any():
            x = block["time_h"]
            xlabel = "Time (h)"
        else:
            x = np.arange(len(block))
            xlabel = "Held-out point"
        ax.scatter(x, block["observed_normalized"], color="#7e0909", s=26,
                   label="Observed")
        ax.plot(x, block["predicted_normalized"], color="#5d5d2a", lw=2,
                marker="o", ms=3, label="Predicted")
        ax.set_title(name.replace("_", " "), fontsize=9, weight="bold")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Normalized signal / fraction")
        ax.grid(axis="y", color="#C7C3AC", alpha=0.45, lw=0.7)
    for ax in axes.flat[len(names):]:
        ax.axis("off")
    axes[0, 0].legend()
    fig.suptitle("Calibration and cross-condition proxy benchmarks", fontsize=13,
                 weight="bold", color="#5d5d2a")
    fig.text(0.5, 0.01,
             "Human observations support a separate conditional calibration; they are not independent validation.",
             ha="center", color="#7e0909")
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    _save(fig, output_dir, "fig07_benchmark_validation")


def plot_uncertainty(summary: pd.DataFrame, sensitivity: pd.DataFrame,
                     output_dir: Path) -> None:
    ordered = summary.set_index("system").loc[SYSTEM_ORDER].reset_index()
    y = np.arange(4)
    med = ordered["median_target_retention_ug_cm2"].to_numpy()
    low = ordered["lower_95_ug_cm2"].to_numpy()
    high = ordered["upper_95_ug_cm2"].to_numpy()
    fig, ax = plt.subplots(figsize=(8.7, 4.8))
    for i, system in enumerate(SYSTEM_ORDER):
        ax.errorbar(
            med[i], y[i],
            xerr=np.array([[med[i] - low[i]], [high[i] - med[i]]]),
            fmt="none", ecolor=COLORS[system], elinewidth=5, capsize=5,
        )
    ax.scatter(med, y, c=[COLORS[x] for x in SYSTEM_ORDER], s=65, zorder=3)
    ax.set_yticks(y, [LABELS[x] for x in SYSTEM_ORDER])
    ax.invert_yaxis()
    ax.set_xlabel("24 h VE + dermis retention (µg cm^-2)")
    scenario_count = int(ordered["scenario_count"].iloc[0])
    ax.set_title(f"Paired {scenario_count}-set scenarios: median and central 95% interval",
                 fontsize=12, weight="bold", color="#5d5d2a")
    ax.grid(axis="x", color="#C7C3AC", alpha=0.5, lw=0.7)
    for i, row in ordered.iterrows():
        ax.text(high[i] + 0.01, i, f"Top frequency={row['probability_best']:.1%}",
                va="center", fontsize=8)
    ax.text(0.5, -0.18,
            "Intervals include transport, surface-entry and skin-condition uncertainty.",
            transform=ax.transAxes, ha="center", color="#7e0909")
    _save(fig, output_dir, "fig08_uncertainty_intervals")

    top = sensitivity.groupby("system", sort=False).head(5).copy()
    labels = list(dict.fromkeys(top["parameter"].tolist()))
    matrix = np.full((len(labels), 4), np.nan)
    for _, row in top.iterrows():
        matrix[labels.index(row["parameter"]), SYSTEM_ORDER.index(row["system"])] = row["spearman_rho"]
    fig, ax = plt.subplots(figsize=(9.5, max(4.8, 0.35*len(labels))))
    project_diverging = LinearSegmentedColormap.from_list(
        "project_diverging", ["#5d5d2a", "#fffaf5", "#7e0909"]
    )
    im = ax.imshow(matrix, cmap=project_diverging, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(4), [LABELS[x].replace("Intact ", "") for x in SYSTEM_ORDER],
                  rotation=12, ha="right")
    ax.set_yticks(np.arange(len(labels)), [x.replace("_", " ") for x in labels])
    for i in range(len(labels)):
        for j in range(4):
            if np.isfinite(matrix[i, j]):
                ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center",
                        color="white" if abs(matrix[i,j]) > 0.55 else "black", fontsize=7)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("Spearman ρ")
    ax.set_title("Top sensitivity drivers of the primary endpoint", fontsize=12,
                 weight="bold", color="#5d5d2a")
    fig.tight_layout()
    _save(fig, output_dir, "fig09_sensitivity")


def create_all_plots(
    results: dict[str, SimulationResult],
    endpoints: pd.DataFrame,
    benchmarks: pd.DataFrame,
    uncertainty_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    output_dir: str | Path,
) -> None:
    configure_style()
    output_dir = Path(output_dir)
    plot_workflow(output_dir)
    plot_concentration_heatmaps(results, output_dir)
    plot_layer_concentrations(results, output_dir)
    plot_mass_and_cumulative(results, output_dir)
    plot_primary_endpoint(endpoints, output_dir)
    plot_benchmarks(benchmarks, output_dir)
    plot_uncertainty(uncertainty_summary, sensitivity, output_dir)
