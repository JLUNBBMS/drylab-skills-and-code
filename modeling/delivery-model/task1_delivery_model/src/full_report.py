"""Assemble the standalone scientific report from the result-backed sections."""
import re
import pandas as pd


def compose_full_report(core, root, table, figures):
    sections={}
    for match in re.finditer(r'^## (\d+)\. ([^\n]+)\n(.*?)(?=^## \d+\. |\Z)',core,re.M|re.S):
        sections[int(match[1])]=re.sub(r'^!\[[^\]]*\]\([^\n]+\)\s*','',match[3],flags=re.M).strip()
    summary=core.split('## 摘要\n',1)[1].split('## 1.',1)[0].strip()
    def read(name):return pd.read_csv(root/'results'/name)
    baseline=read('baseline/baseline_24h_endpoints.csv');e=baseline.set_index('system')
    secondary=read('secondary_endpoints.csv')
    metrics=read('calibration/all_benchmark_metrics.csv')
    numeric=read('numerical_tests.csv')
    roots=read('decision/break_even_surface_P.csv')
    unc=read('uncertainty/uncertainty_summary.csv').set_index('system')
    human=read('decision/human_transfer_metrics.csv').set_index('scenario')
    figure_map={stem:(title,body) for stem,title,body in figures}
    def fig(stem,reading=''):
        title,body=figure_map[stem]
        n=int(stem[3:5])
        return f'\n\n![图{n}　{title}](../figures/{stem}.png)\n\n**图{n}　{title}。** {body}\n\n'+reading+'\n\n'
    def chapter(number,title,body):return f'\n\n## {number}. {title}\n\n{body.strip()}\n'
    report='''# 任务一：tFNA目标皮肤层递送潜力评估完整报告

研究类型：基于文献代理数据的探索性运输建模。比较对象：游离CK、tFNA、NLC和脂质体。目标区域：活性表皮与浅真皮。标准化给药：1 μg/cm²；观察时间：0–24 h。

## 摘要

'''+summary+'''

## 阅读路径

报告依次说明研究用途、证据与数据处理、模型边界、参数校准、数值验证、目标层分布、参数不确定性、人体迁移和选择条件，最后给出实验安排与结论。全文包含1张研究总览图及图1—图12全部正式计算图，每张图均附有读数含义和解释边界。

| 章节 | 内容 | 主要回答的问题 |
|---|---|---|
| 1—2 | 研究目标与全流程 | 模型服务于什么选择，工作怎样衔接？ |
| 3—5 | 证据、方程与校准 | 参数来自哪里，数据约束了什么？ |
| 6—7 | 数值验证与基线结果 | 计算是否可靠，目标层内留下多少？ |
| 8—10 | 情景、迁移与条件边界 | 哪些未知条件可能改变判断？ |
| 11—13 | 实验、复现与结论 | 如何检验结果，能支持什么决定？ |
| 14 | 参考文献 | 原始依据在哪里？ |
'''
    report+=chapter(1,'研究问题与计算边界',sections[1]+'''

“优先候选”表示值得投入下一轮可行性与直接递送验证。判断需同时考虑目标层运输、制剂可制备性和不确定性。运输模型的职责是给出条件性分布预测，并指出能影响选择的观测量；后续实验承担真实CK配方与人体递送的验证。
''')
    workflow='''![研究总览：目标皮肤层递送评估](./任务一_目标层递送流程图.png)

**研究总览。** 上排展示从问题到实验决策的流程；下方A为运输结构示意，B—F分别直接嵌入边界校准、目标层保留、配对情景、人体迁移与持平条件的计算图原文件。计算图保留数据点、曲线、坐标和图例，其具体解释见下文。

| 步骤 | 输入与操作 | 输出及用途 |
|---|---|---|
| 定义目标 | 指定VE与浅真皮为目标，统一结合态剂量和运输条件 | 两层合计保留量及分层暴露指标 |
| 整理证据 | 提取猪皮深度、人皮分层、人体TH21及鼠皮时间数据 | 来源、条件、单位与用途可追溯的代理表 |
| 条件校准 | 用最终有限模型估计有效D，核对边界假设 | 条件参数、曲线残差与结构情景 |
| 数值验证 | 解析解、质量、网格和求解器检查 | 可用于计算比较的实现 |
| 基线模拟 | 四组在统一条件下求解0–24 h运输 | 深度场、分层质量、浓度与AUC |
| 情景与迁移 | 配对抽样；人体数据辅助校准；参数可辨识性检查 | 排序频率和跨条件分布范围 |
| 条件决策 | 计算与固定参照的保留量差及持平边界 | 继续、补测或调整方案所需的条件 |
'''
    report+=chapter(2,'从证据到实验决策的全流程',workflow+fig('fig01_workflow'))
    report+=chapter(3,'证据来源、数据处理与可比性',sections[2]+'''

绝对量和归一化形状在分析中承担不同用途。例如，同一深度保留了自身表面信号的较高比例，说明衰减较慢；只有在进入剂量、检测响应和其他条件可比时，才可能进一步比较绝对运输量。因此本任务将共同表面进入条件写入基线，并通过Pₛ情景评估这一条件对结果的影响。

证据链中最接近同条件横向比较的是猪皮TH-DOX与LIP-DOX。NLC与游离CK承担参照作用，其输入来源与观测类型不同。统一数学边界提高了计算可比性，但不能消除实验来源之间的差异。
''')
    report+=chapter(4,'运输方程、边界条件与评价指标',sections[3]+'''

| 量 | 定义 | 解释 |
|---|---|---|
| Rtarget | MVE + MD | 24 h目标区域内保留的质量，主指标 |
| MVE、MD | 各目标层当前质量 | 区分表皮与真皮空间分布 |
| AUCVE、AUCD | 各层平均浓度的时间积分 | 分别描述两层的组织暴露 |
| Msink | 500 μm底部累计流出质量 | 离开计算区域的运输量 |
| Qinto dermis | MD + Msink | 累计净穿过VE/真皮界面的量 |

高扩散率既可能促进进入目标区域，也可能促进离开目标区域，因此保留量未必随扩散率单调增加。主指标由目标位置决定，界面进入量与sink用于解释其形成过程。
''')
    calibration=sections[4]
    calibration+='\n\n### 5.1 校准数据与代理检验的整体表现\n\n'
    calibration+=table(metrics,{'benchmark':'数据集','usage':'用途','rmse':'RMSE','r2':'R²','n':'观测点数'})
    calibration+=fig('fig07_benchmark_validation',f'''tFNA猪皮有限模型校准的R²为{metrics.iloc[0].r2:.3f}，脂质体为{metrics.iloc[1].r2:.3f}。NLC的两个时间点共同参与拟合，数据量不足以独立验证曲线形状。GSL-7时间曲线来自另一来源，归一化后的R²为{metrics.iloc[4].r2:.3f}；这一检查只约束跨条件时间形状，不能验证CK脂质体的绝对人皮递送。人体直接迁移的偏差在第9节单独处理。''')
    calibration+='\n\n### 5.2 边界一致性与未解释残差\n\n'
    calibration+=fig('fig10_boundary_consistency','半无限参考模型与最终有限模型的曲线不同，说明边界条件参与了有效参数的解释。有限模型的条件校准保持了计算与拟合框架一致，同时保留了无法解释的尾部信号。将深部域扩大到1000和2000 μm后，tFNA参数略有变化，脂质体的平台残差仍然存在，提示仅改变底部位置不足以解释全部观测。')
    report+=chapter(5,'参数校准、代理检验与边界一致性',calibration)
    numerical_intro=sections[9].split('在工作区运行',1)[0].strip()
    numerical=numerical_intro+'\n\n'+table(numeric,{'test':'检查','value':'计算值','threshold':'阈值','passed':'通过'})
    numerical+='''

质量守恒检查对应donor、三层皮肤和sink的总和；非负性检查限制不合理的负质量。主指标网格检查比较生产网格与更细网格，相对差要求低于2%；矩阵指数与BDF在相同条件下交叉核对。单层解析解核对空间离散和时间求解的基本行为。

这些检查证明数值实现符合所定义的方程与边界。它们不验证代理数据能否代表真实tFNA@CK，也不能替代人体和配方实验。
'''
    report+=chapter(6,'数值实现与质量控制',numerical)
    base=sections[5]
    base+='\n\n### 7.1 深度—时间分布\n\n'
    base+=fig('fig02_depth_time_heatmaps','热图显示不同有效运输参数产生的分布宽度。tFNA形成较宽的深部分布；游离CK的高浓度更多集中于SC。游离CK的相对阈值深度较浅，并不意味着其真皮质量为零，绝对保留量应以分层质量表为准。')
    base+='\n\n### 7.2 两个目标层的暴露\n\n'
    base+=fig('fig03_layer_average_concentration',f'''tFNA的VE浓度AUC约为{secondary.set_index('system').loc['tFNA_CK','VE_concentration_AUC_ug_h_cm3']:.2f} μg·h/cm³，真皮为{secondary.set_index('system').loc['tFNA_CK','dermis_concentration_AUC_ug_h_cm3']:.2f} μg·h/cm³。NLC的VE暴露略高，tFNA的真皮暴露略高。两个目标层都与项目相关，因而应同时保留这两种观察。''')
    base+='\n\n### 7.3 质量收支与界面运输\n\n'
    base+=fig('fig04_layer_mass_timecourse','分层曲线用于解释目标层保留如何形成。进入真皮的质量可以继续从底部流出；24 h时tFNA的sink量约为0.0365 μg/cm²，因此累计净进入真皮的量高于真皮当前保留量。模型将这两项分开报告。')
    base+=fig('fig05_cumulative_entry','界面累计净进入曲线具有质量守恒定义，适合描述组织间运输。曲线升高不能单独作为更高局部效益的依据，需同时查看目标层保留与流出。')
    base+='\n\n辅助运输读数如下，通量单位为μg/(cm²·h)：\n\n'
    base+=table(secondary,{'system':'系统','max_net_flux_into_VE_ug_cm2_h':'最大VE净通量','max_net_flux_into_dermis_ug_cm2_h':'最大真皮净通量','operational_lag_h_to_10pct_24h_dermis_entry':'操作性滞后h'})
    base+='\n\n操作性滞后定义为首次达到各组自身24 h累计真皮净进入量10%的采样时间。各组阈值不同，该指标描述相对运输进程，未定义共同药效起效时间。\n\n### 7.4 主指标比较\n\n'
    base+=fig('fig06_primary_endpoint',f'''tFNA与NLC的主指标绝对差约为{e.loc['tFNA_CK','target_retention_ug_cm2']-e.loc['NLC_CK','target_retention_ug_cm2']:.4f} μg/cm²。该差距小于情景范围所显示的波动，适合解释为接近的基线表现。tFNA相对脂质体的基线优势也需保留代理与边界条件限制。''')
    report+=chapter(7,'基线模拟：目标区域保留、暴露与运输',base)
    uncertainty=sections[7]+fig('fig08_uncertainty_intervals',f'''tFNA在指定情景中的排名第一频率为{unc.loc['tFNA_CK','probability_best']:.1%}，主指标中位数为{unc.loc['tFNA_CK','median_target_retention_ug_cm2']:.4f} μg/cm²。六组配对差的中央95%区间均跨零。现有情景不能稳定区分真实制剂表现，也不妨碍将表现有竞争力的载体纳入下一轮验证。''')
    uncertainty+=fig('fig09_sensitivity','在当前抽样范围内，tFNA主指标与表面进入参数的Spearman相关约为0.785，与分配乘子的相关约为0.538。优先测量早期绝对进入量具有直接决策价值。tFNA的D与主指标相关接近零，应结合非单调的条件图解释，不能据此认定扩散不重要。')
    report+=chapter(8,'配对参数情景、不确定性与敏感性',uncertainty)
    report+=chapter(9,'猪皮到人皮的条件性迁移',sections[6]+fig('fig11_human_transfer',f'''直接迁移的R²为{human.loc['direct_transfer','r2']:.3f}，人体辅助拟合为{human.loc['human_assisted','r2']:.3f}。这种改善表明人体数据可以约束特定假设下的有效D，尚不能证明跨物种预测已被独立验证。辅助拟合D约为猪皮条件D的{human.loc['human_assisted','multiplier_vs_pig']:.1%}，该比例适用于本项跨条件情景。'''))
    decision,experiment=sections[8].split('| 下一步测量',1)
    decision+=fig('fig12_decision_boundaries','tFNA基线点靠近与NLC持平的条件线。黑线围成的区域还显示，过低的进入能力或偏离合适范围的扩散尺度均可能降低目标区域的保留量。该图用于提出需要实测的条件，不构成给定配方的成功概率。')
    r=roots[(roots.comparator=='NLC_CK') & (roots.metric=='target_retention_ug_cm2')].iloc[0]
    decision+=f'''在固定基线D及NLC条件下，tFNA表面P的持平值约为{r.surface_P_cm_h:.6f} cm/h，即其基线值的{r.relative_to_baseline_P:.1%}。仅约{(1-r.relative_to_baseline_P)*100:.1f}%的表面进入参数差异即可消除这一小幅基线优势。这一结果使早期进入测量成为选择问题中的关键验证。

持平图固定了对照参数；配对情景则允许各系统参数变化。两种分析应一起阅读：前者提供易理解的条件边界，后者说明整体比较的不确定性。
'''
    report+=chapter(10,'持平条件与选择边界',decision)
    experiment='| 下一步测量'+experiment
    experiment+='''

建议在同一批皮肤、相同CK剂量和覆盖条件下设置游离CK、tFNA、NLC和脂质体对照。可考虑0、1、3、6、12、24 h时间点，并依据实际资源缩减。每次测量记录donor、SC、VE、浅真皮与receiver的CK质量，配合皮层厚度、总回收率和载体完整性读数。采样时间与样本量需由可检测信号、供体变异和实验资源确定，模拟点数不作为实验重复数。

早期数据有助于约束进入与分配，后期分层数据检验深部分布和持续保留。应将部分独立供体或整套独立实验留作验证，而非随机拆分同一条深度曲线的点后宣称外部验证。真实观察偏离预测时，首先检查绝对进入量、释放或载体解体、皮肤条件和模型边界，再决定是否需要更复杂的运输机制。
'''
    report+=chapter(11,'后续实验安排与继续研究的判据',experiment)
    reproduction='在工作区运行'+sections[9].split('在工作区运行',1)[1]
    reproduction+='''

| 文件或目录 | 内容 |
|---|---|
| data/processed | 代理数据、预处理结果与证据矩阵 |
| results/calibration | 条件参数、拟合预测与代理检验 |
| results/baseline | 分层质量、浓度场与24 h端点 |
| results/secondary_endpoints.csv | 分层AUC、通量与操作性滞后 |
| results/uncertainty | 256组输入、1024行输出、配对差与敏感性 |
| results/decision | 边界一致性、人体迁移、可辨识性与持平条件 |
| results/numerical_tests.csv | 数值检查及阈值 |
| results/task2_interface.csv | 下游载体结合态基线时间序列 |
| figures | 图1—图12的PNG和SVG文件 |
| output | 完整、简要、图解报告及配套工作簿、流程图 |

完整报告以相同结果表生成，可通过 `python task1_delivery_model/render_reports.py --full-only` 输出Markdown报告。装载、细胞摄取和药效参数应在各自证据模块中记录，任务二接口不代表这些过程已被任务一验证。
'''
    report+=chapter(12,'复现、数据交付与任务二接口',reproduction)
    conclusion=f'''本任务将“tFNA是否值得开展后续研究”落实为一个可检验的运输问题：在统一剂量和明确的结合态运输假设下，比较活性表皮与浅真皮的保留量，并考察进入能力、边界条件和人体迁移误差对选择的影响。

**基线结果支持tFNA具有目标皮肤层递送潜力。** 24 h两层合计保留量为{e.loc['tFNA_CK','target_retention_ug_cm2']:.4f} μg/cm²，与NLC的{e.loc['NLC_CK','target_retention_ug_cm2']:.4f} μg/cm²接近；tFNA更偏向真皮，NLC和脂质体的表皮保留更高。两个目标层都与项目有关，选择不能仅依据穿透深度或累计真皮进入量。

**现有模型支持条件性候选选择。** tFNA在设定情景中具有较高的主指标中位数和排名第一频率，但六组配对差区间均跨零。有限域残差、代理货物差异及人体直接迁移偏差说明，模型尚未建立真实tFNA@CK在人皮中稳定优于其他载体的证据。

**下一步优先验证的量已经明确。** tFNA与NLC的主指标持平条件靠近基线，表面进入参数与分配参数对判断尤其重要。早期CK绝对进入量、两层CK分布及载体完整性能够直接检验当前运输假设，并决定是否继续投入、调整配方或并行保留对照。

因此，在装载和稳定性可行性获得支持的前提下，本任务为优先开展tFNA@CK的直接递送验证提供了依据。其研究价值在于把一个有文献动机的候选转化为带有明确条件和验证路径的项目选择。后续实验结果应决定这一选择能否继续成立。
'''
    report+=chapter(13,'结论',conclusion)
    report+=chapter(14,'参考文献',sections[10])
    return report
