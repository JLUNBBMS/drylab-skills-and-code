from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .calibration import (_pig_profile, _fit_profile, finite_profile,
                          fit_finite_profile, regression_metrics)
from .model import Geometry, simulate
from .plots import COLORS, LABELS, configure_style, _save


def run_decision_analysis(root: Path, systems, geometry: Geometry):
    """Conditional calibration, transport stress scenarios and decision boundaries."""
    out = root / "results" / "decision"
    out.mkdir(parents=True, exist_ok=True)
    data = root / "data" / "processed"
    audit, predictions, domains = [], [], []
    for system, source in [("tFNA_CK", "TH-DOX"), ("liposome_CK", "LIP-DOX")]:
        f = _pig_profile(data, source)
        x, y = f.depth_um.to_numpy(), f.normalized_raw_to_surface.to_numpy()
        da, fa, ma = _fit_profile(x, y, 24.)
        df = systems[system].diffusion_cm2_h[0]
        for name, d, pred in [
            ("semi_infinite_reference", da, fa.predicted_normalized.to_numpy()),
            ("finite_domain_with_reference_D", da, finite_profile(x, da, geometry)),
            ("finite_domain_calibration", df, finite_profile(x, df, geometry))]:
            audit.append(dict(system=system, model=name, D_cm2_h=d,
                              **regression_metrics(y, pred)))
            predictions.extend(dict(system=system, model=name, depth_um=float(xx),
                observed_normalized=float(yy), predicted_normalized=float(pp))
                for xx, yy, pp in zip(x, y, pred))
        # Deeper sinks probe boundary-model uncertainty. These are assumed
        # computational domains, not claims about the experimental skin thickness.
        for total in [500., 1000., 2000.]:
            geo = replace(geometry, dermis_um=total-geometry.sc_um-geometry.ve_um)
            dd, _, mm = fit_finite_profile(x, y, geo)
            par = replace(systems[system], diffusion_cm2_h=(dd,)*3)
            ep = simulate(par, geometry, times_h=[0.,24.], solver="BDF").endpoint()
            domains.append(dict(system=system, assumed_fit_domain_um=total,
                D_cm2_h=dd, standardized_500um_target_retention=ep["target_retention_ug_cm2"], **mm))
    pd.DataFrame(audit).to_csv(out / "boundary_consistency_metrics.csv", index=False)
    pred_frame = pd.DataFrame(predictions)
    pred_frame.to_csv(out / "boundary_consistency_profiles.csv", index=False)
    pd.DataFrame(domains).to_csv(out / "boundary_domain_scenarios.csv", index=False)

    human = pd.read_csv(data / "wiraja2019_human_th21_depth.csv")
    x, y = human.depth_um.to_numpy(), human.normalized_to_surface.to_numpy()
    dh, fh, mh = fit_finite_profile(x, y, geometry)
    base = systems["tFNA_CK"]
    dp = base.diffusion_cm2_h[0]
    human_profiles, human_metrics, scenario_rows = [], [], []
    for name, dd, usage in [("direct_transfer", dp, "cross_condition_check"),
                           ("human_assisted", dh, "conditional_calibration")]:
        pp = finite_profile(x, dd, geometry)
        human_metrics.append(dict(scenario=name, usage=usage, D_cm2_h=dd,
            multiplier_vs_pig=dd/dp, **regression_metrics(y, pp)))
        human_profiles.extend(dict(scenario=name, depth_um=float(xx),
            observed_normalized=float(yy), predicted_normalized=float(pr))
            for xx, yy, pr in zip(x,y,pp))
    for multiplier in np.geomspace(min(dh/dp,1.), max(dh/dp,1.), 9):
        p = replace(base, diffusion_cm2_h=(dp*multiplier,)*3)
        result = simulate(p, geometry, times_h=np.linspace(0,24,97), solver="BDF")
        ep = result.endpoint()
        ep["D_multiplier"] = multiplier
        for layer in ["VE", "dermis"]:
            mask = result.mesh.skin_layer.eq(layer).to_numpy()
            mean = result.cell_mass[:,mask].sum(axis=1)/result.mesh.loc[mask,"volume_cm3"].sum()
            ep[layer+"_AUC_ug_h_cm3"] = float(np.trapezoid(mean,result.times_h))
        scenario_rows.append(ep)
    conditional = []
    for ps in np.geomspace(1e-4, 1e-2, 5):
        dd, _, mm = fit_finite_profile(x,y,geometry,ps)
        ep = simulate(replace(base,diffusion_cm2_h=(dd,)*3,
            surface_permeability_cm_h=ps), geometry, times_h=[0,24],solver="BDF").endpoint()
        conditional.append(dict(surface_P_cm_h=ps, D_cm2_h=dd,
            target_retention_ug_cm2=ep["target_retention_ug_cm2"], **mm))
    pd.DataFrame(human_profiles).to_csv(out/"human_transfer_profiles.csv",index=False)
    pd.DataFrame(human_metrics).to_csv(out/"human_transfer_metrics.csv",index=False)
    pd.DataFrame(scenario_rows).to_csv(out/"human_transfer_scenarios.csv",index=False)
    pd.DataFrame(conditional).to_csv(out/"human_identifiability.csv",index=False)

    def endpoint(dmult, ps):
        p = replace(base, diffusion_cm2_h=tuple(dmult*d for d in base.diffusion_cm2_h),
                    surface_permeability_cm_h=ps)
        return simulate(p, geometry, times_h=[0,24],solver="BDF").endpoint()
    baseline = pd.read_csv(root/"results/baseline/baseline_24h_endpoints.csv").set_index("system")
    # Nonmonotonic target retention requires searching all crossings, not
    # assuming that the fastest transport always maximizes retention.
    d_axis = np.geomspace(.05,4.,21)
    p_axis = np.geomspace(1e-4,1e-2,21)
    rows = []
    for dm in d_axis:
        for ps in p_axis:
            ep = endpoint(dm, ps)
            rows.append(dict(D_multiplier=dm, surface_P_cm_h=ps, **ep))
    grid = pd.DataFrame(rows)
    grid.to_csv(out/"decision_surface.csv",index=False)
    roots = []
    for comparator in ["NLC_CK","liposome_CK"]:
        for metric in ["target_retention_ug_cm2", "VE_mass_ug_cm2", "dermis_mass_ug_cm2"]:
            target = baseline.loc[comparator,metric]
            vals = [endpoint(1.,ps)[metric]-target for ps in p_axis]
            found = []
            for a,b,fa,fb in zip(p_axis[:-1],p_axis[1:],vals[:-1],vals[1:]):
                if fa*fb<0:
                    rt=brentq(lambda ps:endpoint(1.,ps)[metric]-target,a,b,xtol=1e-11)
                    found.append(rt)
                    roots.append(dict(comparator=comparator,metric=metric,
                        target_value=target,surface_P_cm_h=rt,
                        relative_to_baseline_P=rt/base.surface_permeability_cm_h,
                        absolute_residual=abs(endpoint(1.,rt)[metric]-target), status="crossing"))
            if not found:
                roots.append(dict(comparator=comparator,metric=metric,target_value=target,
                    surface_P_cm_h=np.nan,relative_to_baseline_P=np.nan,
                    absolute_residual=np.nan,status="no_crossing_in_scanned_range"))
    roots_frame = pd.DataFrame(roots)
    roots_frame.to_csv(out/"break_even_surface_P.csv",index=False)

    checks = [dict(check="baseline_target_mass_identity", passed=bool(np.allclose(
        baseline.target_retention_ug_cm2,baseline.VE_mass_ug_cm2+baseline.dermis_mass_ug_cm2,atol=1e-10))),
        dict(check="human_assisted_shape_fit_improves_rmse",passed=human_metrics[1]["rmse"]<human_metrics[0]["rmse"]),
        dict(check="decision_grid_mass_conservation",passed=bool(grid.mass_balance_error.abs().max()<1e-7)),
        dict(check="decision_root_residual",passed=bool(roots_frame.absolute_residual.dropna().lt(1e-6).all())),
        dict(check="decision_grid_physical_retention",passed=bool(grid.target_retention_ug_cm2.between(0,1).all()))]
    pd.DataFrame(checks).to_csv(out/"decision_checks.csv",index=False)
    if not all(c["passed"] for c in checks):
        raise RuntimeError("Decision analysis verification failed")
    plot_decisions(root, pred_frame, pd.DataFrame(human_profiles),
                   pd.DataFrame(scenario_rows), grid, baseline)


def plot_decisions(root, audit, human, scenarios, grid, baseline):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    configure_style()
    out=root/"figures"
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    names={"semi_infinite_reference":"Semi-infinite shape model",
        "finite_domain_with_reference_D":"Finite domain, reference D",
        "finite_domain_calibration":"Finite-domain shape calibration"}
    for ax,sys in zip(axes,["tFNA_CK","liposome_CK"]):
        blocks=audit[audit.system.eq(sys)]
        obs=blocks.drop_duplicates("depth_um")
        ax.scatter(obs.depth_um,obs.observed_normalized,c="#7e0909",s=18,label="Observed proxy")
        for (name,color,style) in zip(names,["#DBA997","#C7C3AC","#5d5d2a"],["--",":","-"]):
            b=blocks[blocks.model.eq(name)]
            ax.plot(b.depth_um,b.predicted_normalized,color=color,ls=style,label=names[name])
        ax.set(title=LABELS[sys],xlabel="Depth (µm)",ylabel="Surface-normalized signal")
    axes[0].legend(fontsize=7)
    fig.suptitle("Boundary assumptions and conditional shape calibration",color="#5d5d2a",weight="bold")
    fig.tight_layout();_save(fig,out,"fig10_boundary_consistency")
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for name,color in [("direct_transfer","#DBA997"),("human_assisted","#7e0909")]:
        b=human[human.scenario.eq(name)]
        axes[0].plot(b.depth_um,b.predicted_normalized,color=color,label=name.replace("_"," "))
    b=human.drop_duplicates("depth_um")
    axes[0].scatter(b.depth_um,b.observed_normalized,c="#5d5d2a",s=16,label="Human TH21 proxy")
    axes[0].set(xlabel="Depth (µm)",ylabel="Surface-normalized signal")
    axes[0].legend(fontsize=8)
    for col,label,color in [("target_retention_ug_cm2","VE + dermis","#7e0909"),
        ("VE_mass_ug_cm2","VE","#DBA997"),("dermis_mass_ug_cm2","Dermis","#5d5d2a")]:
        axes[1].plot(scenarios.D_multiplier,scenarios[col],label=label,color=color)
    axes[1].set(xscale="log",xlabel="Cross-condition D multiplier",ylabel="24 h retention (µg cm^-2)")
    axes[1].legend(fontsize=8)
    fig.suptitle("Human-assisted scenarios: conditional calibration, not independent validation",fontsize=11,color="#5d5d2a",weight="bold")
    fig.tight_layout();_save(fig,out,"fig11_human_transfer")
    fig,axes=plt.subplots(1,2,figsize=(11,4.6))
    cmap=LinearSegmentedColormap.from_list("decision",["#5d5d2a","#fffaf5","#7e0909"])
    pivot=grid.pivot(index="surface_P_cm_h",columns="D_multiplier",values="target_retention_ug_cm2")
    for ax,comp in zip(axes,["NLC_CK","liposome_CK"]):
        delta=pivot.to_numpy()-baseline.loc[comp,"target_retention_ug_cm2"]
        lim=max(abs(delta.min()),abs(delta.max()))
        im=ax.pcolormesh(pivot.columns,pivot.index,delta,cmap=cmap,vmin=-lim,vmax=lim,shading="auto")
        if delta.min()<0<delta.max():
            ax.contour(pivot.columns,pivot.index,delta,levels=[0],colors="#333333",linewidths=1.2)
        ax.scatter([1],[.0015],marker="*",s=80,color="#7e0909",edgecolors="white",zorder=4)
        ax.set(xscale="log",yscale="log",xlabel="tFNA D / baseline D",ylabel="tFNA surface P (cm h^-1)",
               title="tFNA minus "+comp.replace("_CK",""))
        fig.colorbar(im,ax=ax,label="Target retention difference (µg cm^-2)")
    fig.suptitle("Decision conditions: fixed comparator baseline; black line = equal retention",fontsize=11,color="#5d5d2a",weight="bold")
    fig.tight_layout();_save(fig,out,"fig12_decision_boundaries")
