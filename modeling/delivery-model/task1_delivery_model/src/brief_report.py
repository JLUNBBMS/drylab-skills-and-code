"""Concise, result-backed account of the exploratory delivery study."""
import pandas as pd


def compose_brief_report(root):
    def read(name):return pd.read_csv(root/'results'/name)
    e=read('baseline/baseline_24h_endpoints.csv').set_index('system')
    u=read('uncertainty/uncertainty_summary.csv').set_index('system')
    h=read('decision/human_transfer_metrics.csv').set_index('scenario')
    roots=read('decision/break_even_surface_P.csv')
    r=roots[(roots.comparator=='NLC_CK') & (roots.metric=='target_retention_ug_cm2')].iloc[0]
    names={'free_CK':'游离 CK','tFNA_CK':'tFNA','NLC_CK':'NLC','liposome_CK':'脂质体'}
    baseline='| 系统 | 活性表皮保留 | 浅真皮保留 | 两层合计保留 |\n|---|---:|---:|---:|\n'
    uncertainty='| 系统 | 中位数 | 中央95%情景区间 | 排名第一频率 |\n|---|---:|---:|---:|\n'
    for key,label in names.items():
        row=e.loc[key];s=u.loc[key]
        baseline+=f'| {label} | {row.VE_mass_ug_cm2:.4f} | {row.dermis_mass_ug_cm2:.4f} | {row.target_retention_ug_cm2:.4f} |\n'
        uncertainty+=f'| {label} | {s.median_target_retention_ug_cm2:.4f} | {s.lower_95_ug_cm2:.4f}–{s.upper_95_ug_cm2:.4f} | {s.probability_best:.1%} |\n'
    margin=(e.loc['tFNA_CK','target_retention_ug_cm2']/e.loc['NLC_CK','target_retention_ug_cm2']-1)*100
    return f'''# 任务一：tFNA目标皮肤层递送潜力评估简要报告

## 1. 研究目的

本任务是一项前置探索：评估tFNA是否值得作为CK递送的优先验证对象，并明确下一步应先测什么。目标区域包括活性表皮与浅真皮，主要关注药物当量在这两层中的保留和分布。

**主要发现：tFNA在模型中表现出有竞争力的目标层保留量，与NLC的基线结果接近，分布更偏向真皮。** 这一结果为继续验证提供了运输方面的依据，真实tFNA@CK的表现仍需装载、稳定性和直接递送实验确认。

## 2. 研究怎样开展

研究按“文献数据整理—参数校准—统一运输模拟—不确定性与人体迁移分析—实验决策”的流程展开。

| 环节 | 方法与用途 |
|---|---|
| 证据来源 | tFNA与脂质体采用同条件猪皮DOX深度曲线；NLC采用人皮PPD分层数据；游离CK采用经验通透关系 |
| 统一比较 | 四组均给药1 μg/cm²，观察24 h；模型包含有限表面储库、角质层、活性表皮、浅真皮及底部流出区域 |
| 参数校准 | 使用最终有限模型拟合有效扩散参数，检查边界条件与曲线残差 |
| 主要指标 | 24 h活性表皮与浅真皮合计保留量；两层暴露及底部流出量分别报告 |
| 条件分析 | 256组配对参数情景、人体数据辅助校准，以及441个运输条件下的持平分析 |

载体组模拟的是**零释放条件下的结合态CK当量**。代理曲线主要约束分布形状，绝对递送量还依赖表面进入和分配假设。它们尚不能作为真实CK制剂的直接测量。模型通过了18项数值检查和5项决策分析检查。

## 3. 目标皮肤层中的主要结果

下表为标准化基线下的24 h保留量，单位均为μg/cm²。底部流出量不计入目标层保留。

{baseline}

![24 h目标层合计保留量](../figures/fig06_primary_endpoint.png)

**图1　目标区域内的保留量。** 柱高为活性表皮与浅真皮质量之和，表示共同运输条件下的基线计算结果。

tFNA的两层合计保留量比NLC高约**{margin:.2f}%**，两者总体接近。tFNA的真皮保留较高，NLC和脂质体的表皮保留较高；分层浓度的时间积分也呈现相应的空间差异。因此，tFNA的研究价值应结合两个目标层的需求判断。

256组配对参数情景的主指标分布如下，保留量单位为μg/cm²：

{uncertainty}

tFNA的中位数和排名第一频率较高，但六组两两差值的中央95%情景区间均跨零。**现有结果支持候选选择，尚不能证明稳定优于其他真实制剂。** 表中的频率反映指定参数范围内的模拟排序，不能解释为实验成功概率；情景样本也不等同于生物学重复。

## 4. 哪些条件可能改变判断

**表面进入能力。** 在其他条件固定时，tFNA与NLC两层保留量持平的表面进入参数约为{r.surface_P_cm_h:.6f} cm/h，相当于tFNA基线值的{r.relative_to_baseline_P:.1%}。这意味着进入参数下降约{(1-r.relative_to_baseline_P)*100:.1f}%，就可能消除当前的小幅优势。早期CK绝对进入量因此是优先测量对象。

**人体迁移。** 猪皮参数直接用于人体TH21曲线时，R²为{h.loc['direct_transfer','r2']:.3f}；利用人体数据辅助校准后，R²为{h.loc['human_assisted','r2']:.3f}，有效扩散参数约为猪皮条件值的{h.loc['human_assisted','multiplier_vs_pig']:.1%}。这一比例包含物种、载荷和实验差异，仅用于本项条件情景。人体数据参与了拟合，独立验证需要另一套相关数据。

**模型边界与代理误差。** 深部非零荧光、脂质体曲线的平台等现象，不能由当前单一有效扩散参数完全解释。不同边界深度的分析保留了这一限制。模型结果应作为后续检验的依据，而非已经确定的配方性能。

## 5. 结论与下一步

**在装载与稳定性可行的前提下，任务一为优先开展tFNA@CK直接递送验证提供了依据。** 它显示tFNA在目标皮肤层具有值得研究的运输表现，同时指出：与NLC的差距较小，实际进入能力和人体条件可能改变选择。

下一轮优先完成三项测量：

1. **早期绝对进入量：**记录donor、皮肤与receiver中的CK质量，约束进入参数和总回收。
2. **两层分布与持续暴露：**分别测量活性表皮和真皮的CK时间变化，检验保留量与空间偏向。
3. **结合态与完整性：**联合CK定量、载体标记及结构完整性读数，检验模型的运输状态假设。

若实测约束支持有竞争力的目标层保留，且装载和稳定性可行，可继续优先投入tFNA；若结果落入对照更有利的条件区域，则调整配方或并行验证对照。模型的作用是使这一选择有可检验的条件，并让后续实验直接回应关键未知量。

完整方法、全部图像与参考文献见[完整报告](./任务一_递送建模横向比较完整报告.md)；逐图说明见[图解报告](./任务一_递送建模横向比较图解报告.md)。
'''
