from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.sparse import csc_matrix, lil_matrix
from scipy.sparse.linalg import expm_multiply


@dataclass(frozen=True)
class Geometry:
    sc_um: float = 15.0
    ve_um: float = 85.0
    dermis_um: float = 400.0
    donor_film_um: float = 100.0
    area_cm2: float = 1.0

    @property
    def total_um(self) -> float:
        return self.sc_um + self.ve_um + self.dermis_um


@dataclass(frozen=True)
class SystemParameters:
    system: str
    state_label: str
    diffusion_cm2_h: tuple[float, float, float]
    partition: tuple[float, float, float]
    surface_permeability_cm_h: float
    dose_ug_cm2: float = 1.0
    release_rate_h: float = 0.0
    evidence_label: str = ""

    def validate(self) -> None:
        if self.system != "free_CK" and self.release_rate_h != 0.0:
            raise ValueError("Task-one scope gate: carrier release_rate_h must equal 0.")
        if len(self.diffusion_cm2_h) != 3 or len(self.partition) != 3:
            raise ValueError("Exactly three layer values are required.")
        if min(self.diffusion_cm2_h) <= 0 or min(self.partition) <= 0:
            raise ValueError("Diffusion and partition values must be positive.")
        if self.surface_permeability_cm_h <= 0:
            raise ValueError("surface_permeability_cm_h must be positive.")


@dataclass
class SimulationResult:
    system: str
    times_h: np.ndarray
    states: np.ndarray
    matrix: csc_matrix
    mesh: pd.DataFrame
    geometry: Geometry
    parameters: SystemParameters

    @property
    def reservoir_mass(self) -> np.ndarray:
        return self.states[:, 0]

    @property
    def cell_mass(self) -> np.ndarray:
        return self.states[:, 1:-1]

    @property
    def sink_mass(self) -> np.ndarray:
        return self.states[:, -1]

    @property
    def concentration(self) -> np.ndarray:
        volumes = self.mesh["volume_cm3"].to_numpy()
        return self.cell_mass / volumes[None, :]

    def layer_mass_frame(self) -> pd.DataFrame:
        rows: list[dict[str, float | str]] = []
        layers = self.mesh["skin_layer"].to_numpy()
        for time_index, time_h in enumerate(self.times_h):
            masses: dict[str, float] = {}
            for layer in ("SC", "VE", "dermis"):
                masses[layer] = float(self.cell_mass[time_index, layers == layer].sum())
            total = float(
                self.reservoir_mass[time_index]
                + sum(masses.values())
                + self.sink_mass[time_index]
            )
            rows.append(
                {
                    "system": self.system,
                    "time_h": float(time_h),
                    "reservoir_mass_ug_cm2": float(self.reservoir_mass[time_index]),
                    "SC_mass_ug_cm2": masses["SC"],
                    "VE_mass_ug_cm2": masses["VE"],
                    "dermis_mass_ug_cm2": masses["dermis"],
                    "sink_mass_ug_cm2": float(self.sink_mass[time_index]),
                    "cumulative_net_into_VE_ug_cm2": masses["VE"]
                    + masses["dermis"]
                    + float(self.sink_mass[time_index]),
                    "cumulative_net_into_dermis_ug_cm2": masses["dermis"]
                    + float(self.sink_mass[time_index]),
                    "total_mass_ug_cm2": total,
                    "mass_balance_error": total - self.parameters.dose_ug_cm2,
                }
            )
        return pd.DataFrame(rows)

    def concentration_frame(self, parameter_set_id: str = "baseline") -> pd.DataFrame:
        concentration = self.concentration
        rows: list[pd.DataFrame] = []
        bound_column = (
            "free_ck_concentration_ug_cm3"
            if self.system == "free_CK"
            else "carrier_bound_ck_concentration_ug_cm3"
        )
        for i, time_h in enumerate(self.times_h):
            block = self.mesh[
                ["depth_um", "skin_layer", "cell_index", "dx_um"]
            ].copy()
            block.insert(0, "system", self.system)
            block.insert(1, "time_h", float(time_h))
            block[bound_column] = concentration[i]
            if self.system == "free_CK":
                block["carrier_bound_ck_concentration_ug_cm3"] = 0.0
            else:
                block["free_ck_concentration_ug_cm3"] = 0.0
            block["parameter_set_id"] = parameter_set_id
            rows.append(block)
        return pd.concat(rows, ignore_index=True)

    def endpoint(self, time_h: float = 24.0) -> dict[str, float | str]:
        index = int(np.argmin(np.abs(self.times_h - time_h)))
        layer_frame = self.layer_mass_frame().iloc[index]
        conc = self.concentration[index]
        threshold = 0.10 * float(np.max(conc)) if np.max(conc) > 0 else np.inf
        positive = self.mesh.loc[conc >= threshold, "depth_um"]
        penetration = float(positive.max()) if len(positive) else 0.0
        return {
            "system": self.system,
            "time_h": float(self.times_h[index]),
            "net_into_VE_ug_cm2": float(layer_frame["cumulative_net_into_VE_ug_cm2"]),
            "net_into_dermis_ug_cm2": float(
                layer_frame["cumulative_net_into_dermis_ug_cm2"]
            ),
            "dermis_mass_ug_cm2": float(layer_frame["dermis_mass_ug_cm2"]),
            "target_retention_ug_cm2": float(layer_frame["VE_mass_ug_cm2"] + layer_frame["dermis_mass_ug_cm2"]),
            "SC_mass_ug_cm2": float(layer_frame["SC_mass_ug_cm2"]),
            "VE_mass_ug_cm2": float(layer_frame["VE_mass_ug_cm2"]),
            "sink_mass_ug_cm2": float(layer_frame["sink_mass_ug_cm2"]),
            "reservoir_mass_ug_cm2": float(layer_frame["reservoir_mass_ug_cm2"]),
            "penetration_depth_um_10pct": penetration,
            "mass_balance_error": float(layer_frame["mass_balance_error"]),
        }


def build_mesh(
    geometry: Geometry,
    cells_per_layer: tuple[int, int, int] = (24, 68, 160),
) -> pd.DataFrame:
    layers = (
        ("SC", geometry.sc_um, cells_per_layer[0]),
        ("VE", geometry.ve_um, cells_per_layer[1]),
        ("dermis", geometry.dermis_um, cells_per_layer[2]),
    )
    rows: list[dict[str, float | int | str]] = []
    start_um = 0.0
    index = 0
    for layer, thickness_um, count in layers:
        dx_um = thickness_um / count
        for local_index in range(count):
            left_um = start_um + local_index * dx_um
            right_um = left_um + dx_um
            rows.append(
                {
                    "cell_index": index,
                    "skin_layer": layer,
                    "layer_cell_index": local_index,
                    "left_um": left_um,
                    "right_um": right_um,
                    "depth_um": 0.5 * (left_um + right_um),
                    "dx_um": dx_um,
                    "dx_cm": dx_um * 1e-4,
                    "volume_cm3": geometry.area_cm2 * dx_um * 1e-4,
                }
            )
            index += 1
        start_um += thickness_um
    return pd.DataFrame(rows)


def _layer_values(mesh: pd.DataFrame, values: tuple[float, float, float]) -> np.ndarray:
    mapping = {"SC": values[0], "VE": values[1], "dermis": values[2]}
    return mesh["skin_layer"].map(mapping).to_numpy(dtype=float)


def build_transport_matrix(
    mesh: pd.DataFrame,
    geometry: Geometry,
    parameters: SystemParameters,
) -> csc_matrix:
    parameters.validate()
    n_cells = len(mesh)
    matrix = lil_matrix((n_cells + 2, n_cells + 2), dtype=float)
    volumes = mesh["volume_cm3"].to_numpy(dtype=float)
    dx = mesh["dx_cm"].to_numpy(dtype=float)
    diffusion = _layer_values(mesh, parameters.diffusion_cm2_h)
    partition = _layer_values(mesh, parameters.partition)
    donor_volume = geometry.area_cm2 * geometry.donor_film_um * 1e-4
    area = geometry.area_cm2

    # Finite donor to first skin cell. Positive flux is donor -> skin.
    p_top = parameters.surface_permeability_cm_h
    donor_coeff = area * p_top / donor_volume
    cell_coeff = area * p_top / (volumes[0] * partition[0])
    matrix[0, 0] -= donor_coeff
    matrix[0, 1] += cell_coeff
    matrix[1, 0] += donor_coeff
    matrix[1, 1] -= cell_coeff

    # Conservative two-point flux with an equilibrium partition jump.
    for i in range(n_cells - 1):
        resistance = dx[i] / (2 * diffusion[i] * partition[i]) + dx[i + 1] / (
            2 * diffusion[i + 1] * partition[i + 1]
        )
        conductance = area / resistance
        left = i + 1
        right = i + 2
        left_coeff = conductance / (volumes[i] * partition[i])
        right_coeff = conductance / (volumes[i + 1] * partition[i + 1])
        matrix[left, left] -= left_coeff
        matrix[left, right] += right_coeff
        matrix[right, left] += left_coeff
        matrix[right, right] -= right_coeff

    # Bottom Dirichlet sink at the outer face of the final dermis cell.
    bottom_conductance = area * 2 * diffusion[-1] / dx[-1]
    bottom_coeff = bottom_conductance / volumes[-1]
    last = n_cells
    sink = n_cells + 1
    matrix[last, last] -= bottom_coeff
    matrix[sink, last] += bottom_coeff

    return matrix.tocsc()


def initial_state(
    mesh: pd.DataFrame, geometry: Geometry, parameters: SystemParameters
) -> np.ndarray:
    state = np.zeros(len(mesh) + 2, dtype=float)
    state[0] = parameters.dose_ug_cm2 * geometry.area_cm2
    return state


def simulate(
    parameters: SystemParameters,
    geometry: Geometry | None = None,
    cells_per_layer: tuple[int, int, int] = (24, 68, 160),
    times_h: Iterable[float] | None = None,
    solver: str = "expm",
) -> SimulationResult:
    geometry = geometry or Geometry()
    mesh = build_mesh(geometry, cells_per_layer)
    matrix = build_transport_matrix(mesh, geometry, parameters)
    state0 = initial_state(mesh, geometry, parameters)
    times = np.asarray(
        list(times_h) if times_h is not None else np.linspace(0.0, 24.0, 97),
        dtype=float,
    )
    if times[0] != 0 or np.any(np.diff(times) <= 0):
        raise ValueError("times_h must start at 0 and be strictly increasing.")

    if solver == "expm":
        equally_spaced = np.allclose(np.diff(times), np.diff(times)[0])
        if equally_spaced:
            states = expm_multiply(
                matrix,
                state0,
                start=float(times[0]),
                stop=float(times[-1]),
                num=len(times),
                endpoint=True,
            )
        else:
            states = np.vstack([expm_multiply(matrix * t, state0) for t in times])
    elif solver == "BDF":
        solution = solve_ivp(
            lambda _t, state: matrix @ state,
            (float(times[0]), float(times[-1])),
            state0,
            method="BDF",
            t_eval=times,
            rtol=1e-9,
            atol=1e-12,
            jac=matrix,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        states = solution.y.T
    else:
        raise ValueError(f"Unknown solver: {solver}")

    # Roundoff can produce tiny negatives around machine precision only.
    states[np.abs(states) < 1e-14] = 0.0
    return SimulationResult(
        system=parameters.system,
        times_h=times,
        states=states,
        matrix=matrix,
        mesh=mesh,
        geometry=geometry,
        parameters=parameters,
    )


def export_result(
    result: SimulationResult,
    output_dir: str | Path,
    parameter_set_id: str = "baseline",
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.layer_mass_frame().to_csv(
        output_dir / f"{result.system}_layer_mass_timecourse.csv", index=False
    )
    result.concentration_frame(parameter_set_id=parameter_set_id).to_csv(
        output_dir / f"{result.system}_concentration_depth_time.csv", index=False
    )
