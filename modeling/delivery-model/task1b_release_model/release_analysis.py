"""Receiver mass correction and descriptive fitting; no tissue PK extrapolation.

All receiver samples must be CK-free-replaced, well mixed, and reported before
withdrawal. Input concentrations are dilution-corrected assay results. Measured
and synthetic runs use separate output directories and explicit provenance.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.python_packages'))
import json
import hashlib
import argparse
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

RAW_COLUMNS = ['data_kind','curve_id','batch_id','formulation_id','ratio_mg_mg',
 'time_h','initial_ck_ug','initial_receiver_volume_ml','receiver_ck_ug_ml',
 'withdrawn_ml','replaced_ml']
END_COLUMNS = ['curve_id','donor_residual_ck_ug','surface_recovered_ck_ug',
 'precipitation_observed','carrier_integrity_acceptable','notes']

def corrected_curve(g):
    """Q_n=V_n C_n+sum_{i<n}(v_i C_i); post-sample replacement contains no CK."""
    g = g.copy()
    for c in RAW_COLUMNS[4:]:
        g[c] = pd.to_numeric(g[c], errors='raise')
        if not np.isfinite(g[c]).all():
            raise ValueError(f'missing/nonfinite {c}')
    g = g.sort_values('time_h')
    if len(g) < 4 or g.time_h.duplicated().any() or g.time_h.iloc[0] != 0:
        raise ValueError('need >=4 distinct timepoints including time zero')
    if (g[RAW_COLUMNS[4:]] < 0).any().any():
        raise ValueError('negative time, concentration, mass, ratio or volume')
    for c in ['data_kind','batch_id','formulation_id','ratio_mg_mg',
              'initial_ck_ug','initial_receiver_volume_ml']:
        if g[c].nunique(dropna=False) != 1:
            raise ValueError(f'inconsistent {c} within curve')
    mass, volume = float(g.initial_ck_ug.iloc[0]), float(g.initial_receiver_volume_ml.iloc[0])
    if mass <= 0 or volume <= 0:
        raise ValueError('initial mass and receiver volume must be positive')
    removed, q, volumes = 0., [], []
    for row in g.itertuples():
        if volume <= 0 or row.withdrawn_ml > volume:
            raise ValueError('withdrawal exceeds available receiver volume')
        volumes.append(volume)
        q.append(volume * row.receiver_ck_ug_ml + removed)
        removed += row.withdrawn_ml * row.receiver_ck_ug_ml
        volume += row.replaced_ml - row.withdrawn_ml
    g['receiver_volume_before_ml'] = volumes
    g['cumulative_transferred_ck_ug'] = q
    g['fraction_initial_ck'] = np.asarray(q) / mass
    return g

def release_function(t, p, model):
    t = np.asarray(t, float)
    a, tau = p[:2]
    beta = 1. if model == 'first_order' else p[2]
    return a * (-np.expm1(-np.power(t / tau, beta)))

def fit_models(t, y):
    """AICc includes error variance as an estimated parameter. No mechanism inference."""
    t, y = np.asarray(t), np.asarray(y)
    result = []
    for model in ['first_order','weibull']:
        pnum = 2 if model == 'first_order' else 3
        lower = [1e-8,1e-4] + ([0.2] if pnum==3 else [])
        upper = [1.,1e5] + ([5.] if pnum==3 else [])
        fits = []
        for tau in [0.5,4.,16.,80.]:
            x0 = [min(.999,max(.05,float(y.max()))),tau] + ([1.] if pnum==3 else [])
            fits.append(least_squares(lambda p: release_function(t,p,model)-y,
                        x0, bounds=(lower,upper), max_nfev=3000,
                        ftol=1e-11,xtol=1e-11,gtol=1e-11))
        fit = min(fits, key=lambda f: np.sum(f.fun**2))
        sse = float(np.sum(fit.fun**2))
        n, k = len(t), pnum + 1
        aicc = (n*np.log(max(sse/n,1e-30)) + 2*k + 2*k*(k+1)/(n-k-1)) if n>k+1 else np.nan
        # Scale columns before reporting conditioning; raw parameter units differ.
        jac = fit.jac * np.maximum(np.abs(fit.x),1e-8)[None,:]
        condition = float(np.linalg.cond(jac))
        plateau_change = float(release_function([t.max()],fit.x,model)[0] -
                               release_function([t.max()/2],fit.x,model)[0])
        warning=[]
        if fit.x[0] > .999: warning.append('F_infinity_at_upper_bound')
        if condition > 1000: warning.append('ill_conditioned_parameters')
        if plateau_change > .05: warning.append('plateau_not_established')
        if not fit.success: warning.append('optimizer_failed')
        result.append(dict(model=model,F_infinity=float(fit.x[0]),tau_h=float(fit.x[1]),
          beta=float(fit.x[2]) if pnum==3 else 1.,rmse=float(np.sqrt(sse/n)),
          aicc=float(aicc),scaled_jacobian_condition=condition,
          parameter_warning=';'.join(warning),_p=fit.x))
    # Extra shape parameter requires an AICc gain of at least 4 (declared software rule).
    selected=0
    if np.isfinite(result[1]['aicc']) and result[1]['aicc'] < result[0]['aicc']-4:
        selected=1
    for i,r in enumerate(result): r['selected']=i==selected
    return result

def observed_metrics(t, f):
    t,f=np.asarray(t),np.asarray(f)
    out={f'f{x}':float(np.interp(x,t,f)) if t.min()<=x<=t.max() else np.nan for x in [1,8,12,24]}
    out['delta8_12']=out['f12']-out['f8']
    out['t50_observed_h']=np.nan
    out['t50_status']='not_reached_in_observation'
    if np.any(np.diff(f)<-1e-9): out['t50_status']='nonmonotonic_observations'
    elif np.any(f>=.5):
        i=int(np.flatnonzero(f>=.5)[0])
        out['t50_observed_h']=float(t[0]) if i==0 else float(t[i-1]+(.5-f[i-1])*(t[i]-t[i-1])/(f[i]-f[i-1]))
        out['t50_status']='observed_linear_interpolation'
    return out

def validation_gaps(cfg):
    gaps=[k for k,v in cfg['measurement'].items() if (v is not True if k!='validation_record' else not v)]
    for k in ['recovery_min','recovery_max','max_fraction_decrease','max_initial_receiver_fraction']:
        if cfg['qc'][k] is None: gaps.append('qc.'+k)
    return gaps

def bootstrap_mean_ci(values,seed=20260914):
    values=np.asarray(values,float)
    rng=np.random.default_rng(seed)
    means=values[rng.integers(0,len(values),size=(2000,len(values)))].mean(axis=1)
    return np.quantile(means,[.025,.975])

def screen_candidates(metrics,cfg):
    needed=['f1_max','f12_min','f24_min','delta8_12_min','paired_f1_reduction_min']
    missing=[k for k in needed if cfg['decision'].get(k) is None]
    if not cfg['decision'].get('preregistered_at'): missing.append('preregistered_at')
    if not cfg['decision'].get('rationale'): missing.append('rationale')
    if missing: return {'status':'criteria_not_preregistered','missing':missing,'candidates':[]},[]
    if metrics.empty: return {'status':'no_valid_data','candidates':[]},[]
    # No partial success: invalid/missing curves cannot silently improve a formulation.
    summaries=[]
    baseline=metrics[(metrics.ratio_mg_mg==0)&metrics.eligible]
    for ratio,g in metrics.groupby('ratio_mg_mg'):
        if ratio==0: continue
        row={'ratio_mg_mg':float(ratio),'independent_batches':int(g.batch_id.nunique())}
        problems=[]
        if not g.eligible.all(): problems.append('curve_qc_or_method_failure')
        if g.batch_id.duplicated().any(): problems.append('duplicate_batch_curve')
        if g.batch_id.nunique()<cfg['qc']['min_independent_batches']: problems.append('too_few_batches')
        pairs=g.merge(baseline[['batch_id','f1']],on='batch_id',suffixes=('','_control'))
        if len(pairs)!=len(g): problems.append('missing_paired_control')
        if any(g[c].isna().any() for c in ['f1','f12','f24','delta8_12']): problems.append('missing_time_window')
        if not problems:
            d=cfg['decision']
            row.update({f'mean_{c}':float(g[c].mean()) for c in ['f1','f12','f24','delta8_12']})
            reduction=pairs.f1_control.to_numpy()-pairs.f1.to_numpy()
            lo,hi=bootstrap_mean_ci(reduction,cfg['seed'])
            row.update(paired_f1_reduction_mean=float(reduction.mean()),
                       paired_f1_reduction_ci_low=float(lo),paired_f1_reduction_ci_high=float(hi))
            # Require all independent batches to meet illustrative or registered product targets.
            if not ((g.f1<=d['f1_max'])&(g.f12>=d['f12_min'])&(g.f24>=d['f24_min'])&
                    (g.delta8_12>=d['delta8_12_min'])).all(): problems.append('release_window_not_met_in_all_batches')
            if lo<=d['paired_f1_reduction_min']: problems.append('no_resolved_early_release_reduction')
        row['reason']=';'.join(problems)
        row['candidate_for_new_batch_validation']=not problems
        summaries.append(row)
    candidates=[r['ratio_mg_mg'] for r in summaries if r['candidate_for_new_batch_validation']]
    return {'status':'candidates_require_prospective_validation' if candidates else 'no_candidate_meets_rules',
      'candidates':candidates,'not_a_validated_optimum':True,
      'uncertainty_note':'Paired batch bootstrap; with n=3 interval coverage is limited.'},summaries

def analyze(raw, endpoints, cfg, outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    for k,v in cfg['qc'].items():
        if v is not None and (not isinstance(v,(int,float)) or not np.isfinite(v) or v<0):
            raise ValueError(f'invalid qc value: {k}')
    if cfg['qc']['min_independent_batches']<2:
        raise ValueError('at least two independent batches required; three is the exploration default')
    if cfg['qc']['recovery_min'] is not None and cfg['qc']['recovery_max'] is not None:
        if cfg['qc']['recovery_min']>=cfg['qc']['recovery_max']: raise ValueError('recovery limits reversed or equal')
    for k in ['f1_max','f12_min','f24_min','delta8_12_min','paired_f1_reduction_min']:
        v=cfg['decision'].get(k)
        if v is not None and (not isinstance(v,(int,float)) or not np.isfinite(v) or not 0<=v<=1):
            raise ValueError(f'{k} must be a fraction from 0 to 1')
    if list(raw.columns)!=RAW_COLUMNS: raise ValueError('raw input columns must exactly match template')
    if raw.empty: raise ValueError('no observations')
    if set(raw.data_kind.dropna())!={cfg['data_kind']}: raise ValueError('mixed or mismatched measured/simulated provenance')
    if raw[['curve_id','batch_id','formulation_id','data_kind']].isna().any().any(): raise ValueError('missing identifiers')
    if endpoints.curve_id.duplicated().any(): raise ValueError('duplicate endpoint curve_id')
    if raw.groupby('formulation_id').ratio_mg_mg.nunique().max()>1:
        raise ValueError('one formulation_id has multiple ratios')
    if raw.groupby('ratio_mg_mg').formulation_id.nunique().max()>1:
        raise ValueError('multiple formulations at one ratio: analyze separate matched experiments')
    if raw.groupby(['formulation_id','batch_id']).curve_id.nunique().max()>1:
        raise ValueError('multiple curves per formulation/batch: aggregate technical replicates explicitly first')
    curves=[]; summaries=[]; fits=[]; rejected=[]
    gaps=validation_gaps(cfg)
    for cid,g in raw.groupby('curve_id',sort=False):
        try: c=corrected_curve(g)
        except (ValueError,TypeError) as exc:
            rejected.append({'curve_id':cid,'reason':str(exc)})
            continue
        flags=[]
        f=c.fraction_initial_ck.to_numpy();t=c.time_h.to_numpy()
        if (f>1.0+1e-6).any(): flags.append('transferred_mass_exceeds_initial_ck')
        decrease=cfg['qc']['max_fraction_decrease']
        if decrease is not None and np.any(np.diff(f)<-decrease): flags.append('cumulative_fraction_decreased')
        initial=cfg['qc']['max_initial_receiver_fraction']
        if initial is not None and f[0]>initial: flags.append('nonzero_receiver_at_time_zero')
        e=endpoints[endpoints.curve_id==cid]
        recovery=np.nan
        if len(e)!=1: flags.append('missing_endpoint')
        else:
            e=e.iloc[0]
            try:
                residual=float(e.donor_residual_ck_ug);surface=float(e.surface_recovered_ck_ug)
                if not np.isfinite([residual,surface]).all() or min(residual,surface)<0: raise ValueError()
                # Q_end includes receiver immediately BEFORE final withdrawal: never add it twice.
                recovery=(c.cumulative_transferred_ck_ug.iloc[-1]+residual+surface)/c.initial_ck_ug.iloc[0]
            except (ValueError,TypeError): flags.append('invalid_endpoint_mass')
            if str(e.precipitation_observed).lower()!='no': flags.append('precipitation_or_not_checked')
            if str(e.carrier_integrity_acceptable).lower()!='yes': flags.append('carrier_integrity_unconfirmed')
        low,high=cfg['qc']['recovery_min'],cfg['qc']['recovery_max']
        if low is not None and high is not None and np.isfinite(recovery) and not low<=recovery<=high:
            flags.append('mass_recovery_outside_registered_limits')
        eligible=not flags and not gaps
        row=dict(data_kind=cfg['data_kind'],curve_id=cid,batch_id=c.batch_id.iloc[0],formulation_id=c.formulation_id.iloc[0],
          ratio_mg_mg=float(c.ratio_mg_mg.iloc[0]),recovery_fraction=float(recovery),eligible=eligible,
          qc_flags=';'.join(flags),method_gaps=';'.join(gaps),**observed_metrics(t,f))
        summaries.append(row);curves.append(c)
        # Invalid material/method curves may be described but cannot produce intrinsic release fits.
        if eligible:
            for r in fit_models(t,f):
                r.pop('_p');r.update(data_kind=cfg['data_kind'],curve_id=cid,interpretation='descriptive_release_fit_not_mechanism');fits.append(r)
    processed=pd.concat(curves,ignore_index=True) if curves else pd.DataFrame()
    metrics=pd.DataFrame(summaries)
    decision,candidates=screen_candidates(metrics,cfg)
    if rejected:
        decision={'status':'incomplete_or_invalid_input_curves','candidates':[],
                  'rejected_curve_count':len(rejected),'not_a_validated_optimum':True}
        # Avoid leaving a positive secondary candidate table when the full run is invalid.
        for row in candidates:
            row['candidate_for_new_batch_validation']=False
            row['reason']='run_contains_rejected_curves'
    if cfg['data_kind']=='simulated': decision['scope']='SYNTHETIC SOFTWARE DEMO ONLY; NOT A PRODUCT RATIO RECOMMENDATION'
    for row in candidates: row['data_kind']=cfg['data_kind']
    for name,frame in [('corrected_curves',processed),('curve_metrics',metrics),('descriptive_fits',pd.DataFrame(fits)),
                       ('candidate_screen',pd.DataFrame(candidates)),('rejected_curves',pd.DataFrame(rejected))]:
        frame.to_csv(outdir/(name+'.csv'),index=False,encoding='utf-8-sig')
    (outdir/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding='utf-8')
    return decision,metrics,processed

def main():
    p=argparse.ArgumentParser()
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--input',type=Path);source.add_argument('--workbook',type=Path)
    p.add_argument('--endpoints',type=Path)
    p.add_argument('--config',type=Path,default=ROOT/'config.json');p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();cfg=json.loads(args.config.read_text(encoding='utf-8'))
    if args.workbook:
        raw=pd.read_excel(args.workbook,sheet_name='原始观测',usecols=RAW_COLUMNS)
        endpoints=pd.read_excel(args.workbook,sheet_name='终点回收',usecols=END_COLUMNS)
        paths=[args.workbook,args.config]
    else:
        if args.endpoints is None: p.error('--endpoints is required with --input')
        raw=pd.read_csv(args.input);endpoints=pd.read_csv(args.endpoints)
        paths=[args.input,args.endpoints,args.config]
    decision,_,_=analyze(raw,endpoints,cfg,args.output)
    manifest={'data_kind':cfg['data_kind'],'inputs':{str(x):hashlib.sha256(x.read_bytes()).hexdigest()
                 for x in paths},'decision':decision}
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(decision,ensure_ascii=False))

if __name__=='__main__': main()
