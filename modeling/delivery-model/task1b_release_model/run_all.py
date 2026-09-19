"""Build prospective templates, exercise synthetic cases, and write dry-lab outputs."""
from release_analysis import *
import copy
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.linalg import expm

RATIOS=[0.,.5,1.,2.,5.,10.]
TIMES=[0.,.5,1.,2.,4.,8.,12.,24.]
OUTPUT=ROOT/'outputs'/'task1b_20260914'
EVIDENCE=[
 {'id':'E01','topic':'CK 与多糖衍生载体','source':'Micelles modified with a chitosan-derived homing peptide for targeted intracellular delivery of ginsenoside compound K to liver cancer cells',
  'url':'https://pubmed.ncbi.nlm.nih.gov/31887962/','level':'原始研究摘要','supports':'改性壳聚糖胶束中有 CK 持续释放研究','limit':'载体为改性壳聚糖，不能转为寡聚人参多糖或 tFNA 的配比参数','numeric_transfer':'无'},
 {'id':'E02','topic':'CK 与特定水凝胶结构','source':'Triterpenoid saponin-based supramolecular host-guest injectable hydrogels inhibit the growth of melanoma via ROS-mediated apoptosis',
  'url':'https://doi.org/10.1016/j.mser.2024.100824','level':'原始研究摘要（前轮核查）','supports':'HA-CK 与 HA-βCD 构建主客体网络','limit':'化学偶联与注射体系；不是三组分直接混合，本轮出版社全文访问失败','numeric_transfer':'无'},
 {'id':'E03','topic':'释放测量方法','source':'Drug release from nanomedicines: Selection of appropriate encapsulation and release methodology',
  'url':'https://pmc.ncbi.nlm.nih.gov/articles/PMC3482165/','level':'原始研究页面检索文本（前轮）；本轮页面验证阻断','supports':'膜转运可能混淆真实制剂释放','limit':'方法参考，不是 CK 数值来源','numeric_transfer':'无'},
 {'id':'E04','topic':'膜过程建模','source':'Predicting drug release kinetics from nanocarriers inside dialysis bags',
  'url':'https://www.sciencedirect.com/science/article/pii/S0168365919305590','level':'原始研究摘要检索文本；本轮直接打开失败','supports':'用游离药通过膜的资料约束测量过程','limit':'未提取全文数值，本程序未校准本体系膜参数','numeric_transfer':'无'},
 {'id':'E05','topic':'低聚糖原料差异','source':'Antioxidant activities of the oligosaccharides from the roots, flowers and leaves of Panax ginseng C.A. Meyer',
  'url':'https://pubmed.ncbi.nlm.nih.gov/24721081/','level':'原始研究摘要','supports':'根、花、叶来源低聚糖的组成与糖含量有差异','limit':'未研究 tFNA–CK 缓释；项目原料必须独立表征','numeric_transfer':'无'},
 {'id':'E06','topic':'人参多糖表征方法','source':'Fabrication of fluorescent labeled ginseng polysaccharide nanoparticles for bioimaging and their immunomodulatory activity on macrophage cell lines',
  'url':'https://doi.org/10.1016/j.ijbiomac.2017.12.050','level':'原始研究摘要','supports':'人参多糖衍生体系可用 GPC 等方法表征','limit':'西洋参来源并经标记，不等于本项目寡聚糖原料','numeric_transfer':'无'}
]

def save_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def demo_config():
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    cfg['data_kind']='simulated'
    cfg['measurement']={k:True for k in cfg['measurement']}
    cfg['measurement']['validation_record']='SYNTHETIC FIXTURE; NOT AN EXPERIMENTAL VALIDATION'
    cfg['qc'].update(recovery_min=.9,recovery_max=1.1,max_fraction_decrease=.02,max_initial_receiver_fraction=.02)
    cfg['decision'].update(preregistered_at='SYNTHETIC FIXTURE ONLY',rationale='Illustrative software test thresholds, not product specifications',
                          f1_max=.30,f12_min=.40,f24_min=.70,delta8_12_min=.04,paired_f1_reduction_min=.03)
    return cfg

def synthetic_case(case):
    """Generate receiver concentrations from known cumulative masses, then analyze back."""
    rows=[];ends=[];truth=[]
    for b,variation in enumerate([.94,1.,1.06],1):
        for r in RATIOS:
            tau=2.5*variation if case=='null' else (2.5+2*r)*variation
            finf=.9
            if case=='precipitation': finf=.9/(1+r*.20)
            fraction=release_function(np.array(TIMES),[finf,tau],'first_order')
            cid=f'SIM_B{b}_R{r:g}';removed=0.;mass=100.;vol=20.
            for t,f in zip(TIMES,fraction):
                c=(mass*f-removed)/vol
                sample=0. if t==0 else .2
                rows.append(['simulated',cid,f'B{b}',f'R{r:g}',r,t,mass,vol,c,sample,sample])
                removed+=sample*c
            ends.append([cid,mass*(1-fraction[-1]),0.,'yes' if case=='precipitation' and r>0 else 'no','yes','synthetic'])
            truth.append({'curve_id':cid,'F_infinity':finf,'tau_h':tau,'source':'assumed_synthetic'})
    return pd.DataFrame(rows,columns=RAW_COLUMNS),pd.DataFrame(ends,columns=END_COLUMNS),truth

def membrane_demo():
    """Known linear receiver mechanism, used only to demonstrate a confounder."""
    t=np.linspace(0,24,241);data=[]
    for kr,km,label in [(2.,4.,'释放快／膜通过快'),(2.,.08,'释放快／膜通过慢'),(.12,4.,'释放慢／膜通过快')]:
        A=np.array([[-kr,0,0],[kr,-km,0],[0,km,0]])
        x=np.array([expm(A*ti)@np.array([1.,0.,0.]) for ti in t])
        if not np.allclose(x.sum(axis=1),1.,atol=1e-12): raise AssertionError('membrane demo conservation')
        for ti,xi in zip(t,x):
            data.append(dict(time_h=ti,case=label,k_release_h=kr,k_membrane_h=km,
              bound_fraction=xi[0],donor_free_fraction=xi[1],receiver_fraction=xi[2],
              actually_released_fraction=1-xi[0],data_kind='simulated'))
    return pd.DataFrame(data)

def templates():
    d=ROOT/'data'/'templates';d.mkdir(parents=True,exist_ok=True)
    raw=[];end=[];design=[]
    rng=np.random.default_rng(20260914)
    for b in range(1,4):
        order=rng.permutation(RATIOS)
        for r in RATIOS:
            cid=f'B{b}_R{r:g}'
            for t in TIMES:
                raw.append(['measured',cid,f'B{b}',f'R{r:g}',r,t,None,None,None,None,None])
            end.append([cid,None,None,None,None,''])
            design.append({'curve_id':cid,'batch_id':f'B{b}','ratio_mg_mg':r,
              'randomized_order_within_batch':int(np.flatnonzero(order==r)[0])+1,
              'ck_ug_ml':None,'donor_volume_ml':None,'tfna_nM':None,'initial_free_fraction':None,
              'oligosaccharide_lot':'','oligosaccharide_MW_distribution':'','ck_loading_method':'',
              'buffer_and_matrix':'','temperature_C':None,'assay_and_separation_record':''})
    pd.DataFrame(raw,columns=RAW_COLUMNS).to_csv(d/'release_measurements.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(end,columns=END_COLUMNS).to_csv(d/'endpoint_recovery.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(design).to_csv(d/'formulation_metadata.csv',index=False,encoding='utf-8-sig')
    return raw,end,design

def tests():
    checks=[]
    def check(name,fn):
        fn();checks.append({'test':name,'passed':True})
    def demand(ok):
        if not ok: raise AssertionError()
    def raises(fn):
        try:fn()
        except ValueError:return
        raise AssertionError('expected input rejection')
    g=pd.DataFrame([['simulated','x','b','r',0,t,100,10,c,s,p] for t,c,s,p in
                    [(0,0,0,0),(1,1,1,1),(2,2,1,0),(3,3,0,0)]],columns=RAW_COLUMNS)
    check('variable_volume_and_sampling_correction',lambda:demand(np.allclose(corrected_curve(g).cumulative_transferred_ck_ug,[0,10,21,30])))
    check('missing_measurements_rejected',lambda:raises(lambda:corrected_curve(g.assign(receiver_ck_ug_ml=np.nan))))
    check('oversampling_rejected',lambda:raises(lambda:corrected_curve(g.assign(withdrawn_ml=99))))
    check('duplicate_time_rejected',lambda:raises(lambda:corrected_curve(pd.concat([g,g.iloc[[0]]]))))
    check('negative_concentration_rejected',lambda:raises(lambda:corrected_curve(g.assign(receiver_ck_ug_ml=-1))))
    check('t50_is_fraction_of_initial_dose',lambda:demand(np.isnan(observed_metrics([0,1,2,24],[0,.1,.2,.4])['t50_observed_h'])))
    check('late_time_not_extrapolated',lambda:demand(np.isnan(observed_metrics([0,1,2,8],[0,.1,.2,.4])['f24'])))
    check('nonmonotonic_t50_flagged',lambda:demand(observed_metrics([0,1,2,24],[0,.6,.4,.8])['t50_status']=='nonmonotonic_observations'))
    f=fit_models(np.array(TIMES),release_function(TIMES,[.8,5.],'first_order'))
    check('known_first_order_parameters_recovered',lambda:demand(abs(f[0]['tau_h']-5)<1e-4 and abs(f[0]['F_infinity']-.8)<1e-5))
    w=fit_models(np.array(TIMES),release_function(TIMES,[.9,7.,1.8],'weibull'))
    check('known_weibull_shape_recovered',lambda:demand(abs(w[1]['beta']-1.8)<1e-4 and w[1]['selected']))
    check('missing_criteria_cannot_recommend',lambda:demand(screen_candidates(pd.DataFrame(),json.loads((ROOT/'config.json').read_text()))[0]['candidates']==[]))
    check('membrane_model_conservation',lambda:membrane_demo())
    return checks

def figures(cases,mem):
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(15,4.7),sharey=True)
    names={'effect':'假设多糖延缓释放','null':'假设多糖没有作用','precipitation':'假设出现析出或滞留'}
    for ax,(case,proc) in zip(axes,cases.items()):
        for r,g in proc.groupby('ratio_mg_mg'):
            mean=g.groupby('time_h').fraction_initial_ck.mean()
            ax.plot(mean.index,mean.values,label=f'{r:g}∶1',lw=2)
        ax.set(title=names[case],xlabel='时间（h）',xlim=(0,24),ylim=(0,1));ax.grid(alpha=.18)
    axes[0].set_ylabel('累计转移 CK / 初始 CK')
    axes[2].legend(title='假设多糖∶CK',fontsize=8,loc='lower right')
    fig.suptitle('合成情景演示：不同假设会产生不同配比结论',fontsize=15)
    fig.text(.5,.015,'全部曲线由假设参数生成，不是本产品实验结果，不可据此选择配比。',ha='center',color='#9A4C16')
    fig.tight_layout(rect=[0,.05,1,.95])
    fig.savefig(OUTPUT/'合成情景_非实验结果.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for label,g in mem.groupby('case',sort=False):
        axes[0].plot(g.time_h,g.actually_released_fraction,label=label,lw=2)
        axes[1].plot(g.time_h,g.receiver_fraction,label=label,lw=2)
    for ax,title in zip(axes,['实际已从载体释放','受体中观测到的 CK']):
        ax.set(title=title,xlabel='时间（h）',ylabel='占初始 CK 的比例',ylim=(0,1));ax.grid(alpha=.18)
    axes[1].legend(fontsize=8)
    fig.suptitle('膜通过慢，也能产生看似缓释的曲线（合成情景）',fontsize=14)
    fig.tight_layout();fig.savefig(OUTPUT/'膜过程混淆_合成演示.png',dpi=160);plt.close(fig)

def report(checks,decisions):
    sources='\n'.join(f"- {r['id']} [{r['source']}]({r['url']})。{r['supports']}；{r['limit']}。" for r in EVIDENCE)
    text=f'''# task1B 阶段执行报告

2026-09-14｜产品体系：tFNA 装载 CK 后，与寡聚人参多糖混合。

## 本阶段结论

已完成证据分层、首轮实验矩阵、可填写工作簿、可运行释放分析程序，以及合成情景的软件验证。当前目录未发现本体系的实测配比释放数据，因此尚不能确定最佳多糖∶CK 比例，尚未完成湿实验与前瞻配比验证。

现有 task1 将载体运输释放率设为零。task1B 为后续实测分析建立入口；本次没有把代理皮肤曲线转换为新的释放或药效结论，也没有重算人体皮肤运输。

## 证据核查改变了什么

本次定向检索包含 tetrahedral / tetrahedral framework nucleic acids + compound K；ginseng polysaccharide / ginseng oligosaccharide + compound K；water-soluble ginseng oligosaccharides + structure；以及膜释放方法。检索页面中未找到能够直接校准本三组分配比响应的原始数据。这不是对全部文献不存在的证明。

CK 的改性壳聚糖胶束与 HA-CK/HA-βCD 网络研究可以支持研究路线，但不能提供本产品的最优比例。人参低聚糖原料研究提示部位与组成需要记录；未把不同原料作为同一个固定分子处理。所有本体系释放参数均保留待测，没有迁入邻近载体的 k 值。

## 首轮实验已排好

质量比 0、0.5、1、2、5、10 mg/mg，共 6 个主配方，每个配方 3 个独立 tFNA–CK 制备批次。每个批次分装到各比例组，配对比较；批内检测顺序已用固定种子随机化。每条曲线包含 0、0.5、1、2、4、8、12、24 h，共 18 条主曲线、144 条待填观测记录。技术重复进样另行保留，不能当作额外独立批次。

0∶1 为不加多糖的 tFNA–CK。已溶解 CK 膜通过对照、基质空白、必要的空载体混合对照属于额外方法验证，不包含在 18 条主曲线内。工作簿列明这些项目。

各组固定 CK 浓度、tFNA 用量、装载条件、基质与终体积；未知的浓度、体积、装载量、初始游离比例和原料规格均留空，没有自行编造。工作簿中的配料换算在输入完整前保持空白。

## 程序实际完成的工作

1. 按真实取样及补液体积校正累计受体 CK：Qn=Vn×Cn+Σ(i<n)vi×Ci。支持取样量变化和不等量补液；要求补液不含 CK、取样前充分混匀、没有未记录的其他损失。
2. 以初始实测 CK 为分母，报告 F1、F8、F12、F24、8–12 h 新增释放和观察期内 t50。指定时间可在观测区间内线性插值，绝不向 24 h 外推。终点回收率使用取样前受体量加供体残留与表面回收，不重复计入末次样品。
3. 通过质量回收、析出、tFNA 完整性和方法记录检查后，比较一阶与 Weibull 描述性模型。较复杂模型需要 AICc 改善至少 4，此为预设软件选择规则。模型参数触边、条件数较大或末期仍有较大变化时标注参数解释限制。
4. 配比筛选要求预先填写释放窗口和变化阈值，并与同批 0∶1 配对比较。用独立批次自助抽样估计早期释放差异区间；3 批仅供探索，区间覆盖性有限。所有批次满足窗口且有可分辨的早期释放降低，才列为新批次验证候选。
5. 缺少观测、配对对照、预设阈值或关键方法验证时，不推荐比例。观察曲线标记为受体转移；方法未验证时不输出所谓本征释放参数。

当前程序筛选已经实测的比例，不自动对未测比例生成置信区间，也不自动拟合两维配比响应面。获得数据后先检查趋势、变异和材料变化，再决定新比例的插值与前瞻实验。避免在无数据时制造精确推荐。

## 软件验证结果

{len(checks)} 项核心验证已通过，包含变体积取样校正、缺失值与非法输入拦截、t50 分母与外推限制、已知动力学参数恢复、以及膜过程质量守恒。额外端到端回归结果见验证清单。

- “存在配比效应”合成情景能进入候选验证流程。
- “多糖无作用”合成情景没有推荐比例。
- “析出或滞留”合成情景被排除。
- 空白实测模板不能产生推荐比例。

这些是程序行为检查，不是配方有效性验证。合成数据中的剂量、时间常数、变化幅度、回收率和候选规则均为假设，不用作产品参数。示例阈值仅位于演示配置中，实测配置仍为空。

![合成情景演示](合成情景_非实验结果.png)

![膜过程混淆](膜过程混淆_合成演示.png)

## 下一步由什么数据决定

首先测原料规格、tFNA–CK 实际装载与游离比例，并确认 CK 在受体介质中的定量、稳定性、溶解容量及膜/分离方法。若装载不可靠，先处理装载问题；若多糖加入后破坏 tFNA，先调整混合条件。

完成首轮曲线后，先将原始记录复制为独立实测文件，保留模板，再运行分析。将全部同条件配方和批次一起输入。候选必须在独立新批次复核，并在可制备范围内检查不同绝对浓度。最终配方建议需同时包含多糖∶CK、CK 浓度、tFNA 用量、基质、适用条件和验证误差。

只有体外释放与材料状态支持后，才扩展 task1 的结合态/游离态守恒运输。本次不以体外 F(t) 乘原 task1 皮层曲线，也不宣称延长人体护肤功效。

## 来源与访问限制

{sources}

本次未进行可用于校准的文献曲线数值提取。文献支持材料与方法选择，合成曲线支持软件检验，两者均不能替代本体系实测。
'''
    (OUTPUT/'task1B_阶段执行报告.md').write_text(text,encoding='utf-8')

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    raw,end,design=templates()
    pd.DataFrame(EVIDENCE).to_csv(OUTPUT/'evidence_matrix.csv',index=False,encoding='utf-8-sig')
    checks=tests();decisions={};cases={}
    for case in ['effect','null','precipitation']:
        d=ROOT/'demo'/case;d.mkdir(parents=True,exist_ok=True)
        r,e,truth=synthetic_case(case);cfg=demo_config()
        r.to_csv(d/'synthetic_measurements.csv',index=False,encoding='utf-8-sig')
        e.to_csv(d/'synthetic_endpoints.csv',index=False,encoding='utf-8-sig')
        save_json(d/'assumed_parameters.json',truth);save_json(d/'synthetic_config.json',cfg)
        decision,metrics,proc=analyze(r,e,cfg,d/'results')
        decisions[case]=decision;cases[case]=proc
        expected=bool(decision['candidates']) if case=='effect' else not decision['candidates']
        if not expected: raise AssertionError(f'{case}: {decision}')
        checks.append({'test':f'{case}_end_to_end','passed':True})
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    blank_dec,_,_=analyze(pd.DataFrame(raw,columns=RAW_COLUMNS),pd.DataFrame(end,columns=END_COLUMNS),cfg,OUTPUT/'template_check')
    if blank_dec['candidates'] or blank_dec.get('rejected_curve_count')!=18: raise AssertionError('blank template gate')
    checks.append({'test':'blank_measured_template_no_recommendation','passed':True})
    r,e,_=synthetic_case('effect');r.loc[0,'data_kind']='measured'
    try:
        analyze(r,e,demo_config(),OUTPUT/'regression'/'mixed_provenance')
        raise AssertionError('mixed provenance accepted')
    except ValueError:
        checks.append({'test':'mixed_provenance_rejected','passed':True})
    r,e,_=synthetic_case('effect');r.loc[0,'receiver_ck_ug_ml']=np.nan
    bad,_,_=analyze(r,e,demo_config(),OUTPUT/'regression'/'incomplete_curve')
    if bad['candidates'] or bad['status']!='incomplete_or_invalid_input_curves': raise AssertionError('incomplete run gate')
    checks.append({'test':'incomplete_run_suppresses_all_candidates','passed':True})
    r,e,_=synthetic_case('effect');e['surface_recovered_ck_ug']=1000
    bad,_,_=analyze(r,e,demo_config(),OUTPUT/'regression'/'bad_recovery')
    if bad['candidates']: raise AssertionError('mass recovery gate')
    checks.append({'test':'impossible_recovery_no_candidate','passed':True})
    r,e,_=synthetic_case('effect');unvalidated=demo_config()
    unvalidated['measurement']['separation_and_membrane_validated']=False
    bad,_,_=analyze(r,e,unvalidated,OUTPUT/'regression'/'unvalidated_membrane')
    if bad['candidates']: raise AssertionError('method validation gate')
    checks.append({'test':'unvalidated_membrane_no_candidate','passed':True})
    mem=membrane_demo();mem.to_csv(ROOT/'demo'/'membrane_confounding.csv',index=False,encoding='utf-8-sig')
    figures(cases,mem)
    save_json(OUTPUT/'verification.json',checks)
    save_json(OUTPUT/'workbook_content.json',{'design':design,'raw':raw,'end':end,'raw_columns':RAW_COLUMNS,
       'end_columns':END_COLUMNS,'evidence':EVIDENCE,'ratios':RATIOS})
    manifest={'executed_at':datetime.now(timezone.utc).isoformat(),'measured_curves_available':0,
      'status':'dry_lab_pipeline_and_templates_complete; wet_lab_validation_pending',
      'checks_passed':len(checks),'synthetic_scenarios':list(decisions),'real_ratio_recommendation':None,
      'core_file_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [ROOT/'run_all.py',ROOT/'release_analysis.py',ROOT/'config.json']}}
    save_json(OUTPUT/'execution_manifest.json',manifest)
    report(checks,decisions)
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
