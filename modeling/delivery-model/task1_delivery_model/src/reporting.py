from pathlib import Path
import json
import pandas as pd

NAMES = {"free_CK":"游离 CK", "tFNA_CK":"tFNA", "NLC_CK":"NLC", "liposome_CK":"脂质体"}

NAMES.update({"semi_infinite_reference":"半无限形状参考", "finite_domain_with_reference_D":"参考D的有限域计算",
    "finite_domain_calibration":"有限域条件校准", "direct_transfer":"直接迁移", "human_assisted":"人体辅助",
    "cross_condition_check":"跨条件检查", "conditional_calibration":"条件校准",
    "target_retention_ug_cm2":"两层合计", "VE_mass_ug_cm2":"VE保留", "dermis_mass_ug_cm2":"真皮保留",
    "crossing":"有交点", "no_crossing_in_scanned_range":"范围内无交点"})

def table(frame, columns, digits=4):
    rows = ["| " + " | ".join(columns.values()) + " |", "|" + "---|"*len(columns)]
    for _, row in frame.iterrows():
        vals=[]
        for key in columns:
            v=row[key]
            if isinstance(v, float):
                v="—" if pd.isna(v) else (f"{v:.3e}" if 0<abs(v)<.0001 else f"{v:.{digits}f}")
            vals.append(NAMES.get(str(v),str(v)))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)

REFERENCES = """[1] [PubChem：Ginsenoside K](https://pubchem.ncbi.nlm.nih.gov/compound/Ginsenoside-K).

[2] Potts RO, Guy RH. [Predicting skin permeability](https://doi.org/10.1023/A:1015810312465). Pharmaceutical Research. 1992;9:663–669.

[3] Wiraja C, et al. [Framework nucleic acids as programmable carrier for transdermal drug delivery](https://doi.org/10.1038/s41467-019-09029-9). Nature Communications. 2019;10:1147.

[4] Kim MH, et al. [Formulation and evaluation of nanostructured lipid carriers of 20(S)-protopanaxadiol by Box-Behnken design](https://doi.org/10.2147/IJN.S215835). International Journal of Nanomedicine. 2019;14:8509–8520.

[5] Jin Y, et al. [Preparation and evaluation of liposomes and niosomes containing total ginsenosides for anti-photoaging therapy](https://doi.org/10.3389/fbioe.2022.874827). Frontiers in Bioengineering and Biotechnology. 2022;10:874827.

[6] Li Z, et al. [Oral liposomes encapsulating ginsenoside compound K for rheumatoid arthritis therapy](https://doi.org/10.1016/j.ijpharm.2023.123247). International Journal of Pharmaceutics. 2023;643:123247.

[7] [An open-access data set of pig skin anatomy and physiology for modelling purposes](https://pmc.ncbi.nlm.nih.gov/articles/PMC9547536/). 用于跨物种生理参数迁移的方法背景，未提供本项目 tFNA 的通用转换系数。
"""

FIGURES = [
("fig01_workflow","研究流程","从代理证据和统一运输条件出发，经过有限模型校准、数值验证、人体迁移情景与条件边界，形成后续实验的选择依据。流程中的人体辅助校准使用了人体观测，属于参数约束。"),
("fig07_benchmark_validation","代理校准与跨条件检验","红点为文献代理观测，橄榄线为计算值。猪皮 tFNA 与脂质体采用最终有限模型校准；NLC 使用两个分层比例。人体面板展示直接迁移检查，辅助校准见人体迁移图。大鼠脂质体时间曲线属于独立来源的代理形状检验。"),
("fig10_boundary_consistency","边界条件与形状校准","三个模型设定分别为半无限形状参考、参考参数在有限域中的曲线、有限域条件校准。它们检验解析拟合参数与最终计算边界的兼容性。500 μm 处吸收边界固定浓度为零，文献中的非零尾部信号形成结构残差。图中比较的是模型设定，未提供匹配原实验边界的验证。"),
("fig02_depth_time_heatmaps","深度—时间分布","四组共用对数色标，虚线标出 SC/VE 与 VE/真皮界面。纵轴深度向上增大。颜色表示模型浓度，载体组为结合态 CK 当量。高浓度和深部分布应结合目标层保留量阅读，相对分布宽度不能替代绝对质量。"),
("fig03_layer_average_concentration","活性表皮与真皮暴露","两层分别计算平均浓度与浓度 AUC。层体积不同，两个浓度不能直接相加为总质量。表皮较高的暴露与真皮较高的暴露对应不同空间分布；本任务同时将两层作为目标区域。"),
("fig04_layer_mass_timecourse","质量分配","donor、SC、VE、真皮与 sink 构成质量收支。VE 和真皮共同组成主指标，SC 和 donor 为其余位置的保留量，sink 为离开建模区域的量。sink 未纳入目标区保留收益。"),
("fig05_cumulative_entry","界面累计净进入","该图展示穿过组织界面的累计净通量。进入真皮的累计净量等于真皮保留加 sink 量；这是辅助运输指标。它与某时刻的目标层保留量具有不同含义。"),
("fig06_primary_endpoint","目标区域保留量","柱高为 24 h 的 VE 与真皮质量之和。该比较以统一有限剂量、几何、分配和表面进入参数为条件。应结合分层结果及不确定性理解小幅差距。"),
("fig08_uncertainty_intervals","配对情景分布","点为中位数，横线为指定分布下的中央 95% 情景区间，右侧为样本中排名第一的频率。256 组为参数情景，不能当作生物学重复。情景区间与获胜频率均依赖假设范围。"),
("fig09_sensitivity","主指标敏感性","颜色和数值为各输入与两层合计保留量的 Spearman 相关。它用于识别在既定范围内值得优先测量的量。保留量可能随运输速率非单调变化，较小的相关系数也可能掩盖这种关系。"),
("fig11_human_transfer","人体辅助迁移情景","左侧对照猪皮参数直接迁移与人体数据辅助校准；人体观测已用于后者，拟合改善不能作为独立预测验证。右侧只展示 tFNA 跨条件扩散尺度变化时的目标层分布。相同几何和其他参数使该图成为条件性迁移情景。"),
("fig12_decision_boundaries","选择条件与持平边界","横轴为 tFNA 扩散参数相对基线倍数，纵轴为 tFNA 表面进入参数。对照组保持各自基线；颜色表示两层合计保留量差，黑线表示持平，星号表示 tFNA 基线。红色区域支持相对运输优势，橄榄色区域提示对照保留量更高。轮廓由有限网格插值得到，具体单参数交点另用求根核对。")]

def write_reports(root: Path, only=None):
    def read(path): return pd.read_csv(root/"results"/path)
    ep=read("baseline/baseline_24h_endpoints.csv")
    par=read("calibration/calibrated_parameters.csv")
    sec=read("secondary_endpoints.csv")
    unc=read("uncertainty/uncertainty_summary.csv")
    pair=read("uncertainty/pairwise_differences.csv")
    sens=read("uncertainty/sensitivity_spearman.csv")
    audit=read("decision/boundary_consistency_metrics.csv")
    domains=read("decision/boundary_domain_scenarios.csv")
    human=read("decision/human_transfer_metrics.csv")
    hs=read("decision/human_transfer_scenarios.csv")
    hi=read("decision/human_identifiability.csv")
    roots=read("decision/break_even_surface_P.csv")
    tests=read("numerical_tests.csv")
    checks=read("decision/decision_checks.csv")
    e=ep.set_index("system"); h=human.set_index("scenario")
    bt=table(ep,{"system":"系统","VE_mass_ug_cm2":"VE保留","dermis_mass_ug_cm2":"真皮保留","target_retention_ug_cm2":"两层合计","sink_mass_ug_cm2":"底部流出"})
    ut=table(unc,{"system":"系统","median_target_retention_ug_cm2":"中位数","lower_95_ug_cm2":"2.5%分位","upper_95_ug_cm2":"97.5%分位","probability_best":"排名第一频率"})
    at=table(sec,{"system":"系统","VE_concentration_AUC_ug_h_cm3":"VE浓度AUC","dermis_concentration_AUC_ug_h_cm3":"真皮浓度AUC"},2)
    conclusion=(f"标准化基线下，tFNA 的目标层合计保留量为 {e.loc['tFNA_CK','target_retention_ug_cm2']:.4f} μg/cm²，"
      f"NLC 为 {e.loc['NLC_CK','target_retention_ug_cm2']:.4f} μg/cm²，脂质体为 {e.loc['liposome_CK','target_retention_ug_cm2']:.4f} μg/cm²。"
      f"tFNA 与 NLC 的相对差为 {(e.loc['tFNA_CK','target_retention_ug_cm2']/e.loc['NLC_CK','target_retention_ug_cm2']-1)*100:.2f}%，"
      "两者的接近程度应与代理误差和情景范围一起解释。tFNA 的运输表现支持将其列为直接 CK 验证的候选，优先投入还需结合装载可行性与实验资源。模型没有建立真实人皮 CK 制剂的确定性优胜排序。")
    full=f"""# 任务一：目标皮肤层递送潜力评估完整报告

计算对象：游离 CK、tFNA、NLC 与脂质体结合态 CK 当量。目标区域：活性表皮（VE）和浅真皮。给药量：1 μg/cm²；观察窗：0–24 h。

## 摘要

本任务使用文献代理数据约束一维有效运输模型，评估 tFNA 是否具有值得开展直接 CK 实验的目标层递送潜力，并确定可能改变选择的参数条件。主终点为 24 h 活性表皮与浅真皮的合计保留量；分层保留量、层平均浓度 AUC 和底部流出量分别报告。模型追踪零释放条件下的载体结合态 CK 当量。

{conclusion}

人体 TH21 曲线支持单独的跨条件校准。物种、载荷与读出条件共同影响有效参数，因此该分析给出迁移情景。配对不确定性、不同边界深度及持平条件共同界定结论范围。

## 1. 研究问题与决策用途

研究问题是：在已具备稳定结合状态的假设下，tFNA 是否能在 VE 和浅真皮形成有竞争力的运输分布，哪些实验最能检验这一判断？本任务用于安排直接 CK 验证的候选与测量重点。研究对象同时包含两层，因此分别保留其读数，合计质量用于总体目标区比较。

载体组的初始 100% 结合态是剂量归一化定义。装载率、解离动力学、细胞摄取、胞内游离 CK 和药效未进入运输方程。装载与结合能属于独立证据模块，本任务以稳定结合态作为计算前提。

## 2. 证据结构与观测含义

| 对象 | 代理来源 | 本模型用途 | 可比性边界 |
|---|---|---|---|
| tFNA与脂质体 | Wiraja等，同条件猪皮TH-DOX/LIP-DOX，24 h | 深度形状约束 | 同货物、同研究；载体尺寸与构型不同 |
| NLC | Kim等，人尸体皮肤PPD-NLC，3 h与6 h | 真皮占皮肤沉积的比例 | 跨研究、跨货物参照；NLC代表特定脂质纳米载体 |
| 人体TH21 | Wiraja等，人皮裸TH21深度信号 | 跨条件检查与辅助校准 | 物种、载荷、读出差异共同存在 |
| 脂质体GSL-7 | Jin等，大鼠皮肤总人参皂苷时间曲线 | 独立来源的归一化时间形状检验 | 含释放货物的总信号代理 |
| 游离CK | PubChem性质与Potts–Guy关系 | 小分子经验基线 | 对CK皮肤系统的直接适用性仍需测量 |

CK脂质体口服研究提供配方可行性背景，未用于皮肤参数校准。全部皮肤代理读数均缺少足以直接确定本项目完整载体结合态 CK 绝对运输量的信息。数字化曲线的深度点是观测位置，不能作为独立生物学重复数。

猪皮曲线按各自表面信号归一化；tDOX作为游离DOX对照，未用作空白背景。人体TH21预处理为扣除对照、负值截零后按表面归一化。NLC约束为3 h的4/62与6 h的47/150。GSL-7按自身48 h总传输值归一化。

归一化保留了深度衰减形状，却移除了绝对强度尺度。扩散参数主要描述形状；表面进入和分配参数采用显式假设与情景范围。绝对 CK 质量是这些条件共同产生的模型输出。

## 3. 一维有效运输模型

几何由有限donor、SC、VE、浅真皮及底部sink组成。面积为1 cm²，donor厚100 μm；SC为15 μm，VE为85 μm，真皮为400 μm；总深度500 μm。网格为24/68/160个单元，时间采样为97点。

层内运输方程：

`∂Cᵢ/∂t = Dᵢ ∂²Cᵢ/∂x²`

各单元以质量为状态量。内部界面通量按两侧半单元扩散阻力与分配势差计算：

`Jᵢ⟶ⱼ = [Cᵢ/Kᵢ − Cⱼ/Kⱼ] / [Δxᵢ/(2DᵢKᵢ) + Δxⱼ/(2DⱼKⱼ)]`

表面采用有限进入系数：`J₀ = Pₛ(Cdonor − C₁/KSC)`；donor随净进入而减少，也允许反向通量。表面系数表示donor至首个皮肤单元的有效阻力。底部为完全吸收边界，流出质量累积到sink。

`Mdonor + MSC + MVE + MD + Msink = 初始剂量`

载体的三层D相同、K均为1，层名表示几何和结果统计区域；角质层特异阻力、毛囊通道等合并于有效参数。模型描述平均运输行为。零释放条件隔离了载体结合态运输问题；它并非所有配方递送量的严格上界。

主终点：`Rtarget(24 h) = MVE(24 h) + MD(24 h)`，单位μg/cm²。分层AUC是层平均浓度对0–24 h积分，单位μg·h/cm³，两个浓度AUC分别报告。累计净进入真皮为`MD + Msink`，用于辅助描述界面通量。按各组自身最大浓度10%计算的深度仅表示相对分布宽度。

## 4. 参数校准与边界一致性

猪皮深度曲线在0–500 μm范围内使用最终有限模型的归一化观测算子拟合。算子以首个单元浓度代表表面浓度，在网格中心线性插值，吸收边界浓度为零。仅估计一个共同有效D，K=1、Pₛ=0.0015 cm/h固定；优化使用log10(D)，范围10⁻⁹–10⁻² cm²/h，soft-L1损失，尺度0.08。这里的donor和几何为标准化条件，原实验的完整边界条件尚未重建，因此属于条件性有效参数校准。

半无限erfc模型作为边界一致性的参考：`C(x,t)/C(0,t) = erfc[x/(2√(Dt))]`。该参考与有限剂量模型并列检验，最终基线采用有限模型校准参数。

{table(par,{"system":"系统","D_SC_cm2_h":"SC扩散cm²/h","D_VE_cm2_h":"VE扩散cm²/h","D_dermis_cm2_h":"真皮扩散cm²/h","surface_permeability_cm_h":"表面P cm/h"})}

游离CK采用MW=622.9、logP=5.6，`log10(Kp) = −2.72 + 0.71logP − 0.0061MW`。Kp约0.00286 cm/h；KSC/KVE/KD为25/2/1.5，SC扩散系数由Kp×SC厚度/KSC计算，其余层扩散与表面参数属于工程设定。NLC在相同生产网格上，以3 h和6 h分层比例的平方残差共同估计D。

{table(audit,{"system":"系统","model":"模型设定","D_cm2_h":"有效D","rmse":"RMSE","r2":"R²","n":"深度点数"})}

拟合优度描述与输入数据的吻合程度。500 μm处的非零荧光与零浓度边界不兼容；脂质体深部平台还可能反映背景、释放或不同运输路径。模型保留这些残差，单一D无法将其解释为已识别的运输机制。

![边界条件与校准](../figures/fig10_boundary_consistency.png)

将拟合域设为500、1000和2000 μm，继续使用同一0–500 μm数据，再将参数放入统一500 μm评价域，以考察边界模型的不确定性。额外深度是计算假设，不能当作原实验皮肤厚度。

{table(domains,{"system":"系统","assumed_fit_domain_um":"拟合域μm","D_cm2_h":"有效D","r2":"R²","standardized_500um_target_retention":"统一域两层保留"})}

不同拟合域下D与目标层输出的变化表明，形状拟合较好不能独立确定人体绝对递送量。这一结构情景与256组主参数情景分别报告。

## 5. 基线目标层分布

以下质量均为μg/cm²。sink是底部流出量。

{bt}

{conclusion}

{at}

AUC单位为μg·h/cm³。表皮与真皮分别解释；该暴露属于组织平均结合态CK当量，尚未转换为细胞内有效药物浓度。

![目标层保留量](../figures/fig06_primary_endpoint.png)

## 6. 人体辅助迁移分析

先将猪皮条件参数直接用于人体TH21曲线，评估跨条件偏差；再固定相同几何、K和Pₛ，仅使用人体归一化曲线估计D。两种情景共享最终有限模型观测算子。

{table(human,{"scenario":"情景","usage":"证据用途","D_cm2_h":"有效D","multiplier_vs_pig":"相对猪皮D","rmse":"RMSE","r2":"R²"})}

人体辅助参数约为猪皮基线的{h.loc['human_assisted','multiplier_vs_pig']:.3f}倍。该比例合并物种、载荷、皮肤条件和测量方式差异；仅用于本项条件性情景。人体观测参与参数估计，因此辅助拟合结果属于校准。模型尚缺少独立人体CK载体数据用于验证。

在人体辅助D与猪皮D之间设置9个对数间隔情景，保持其他条件固定，观察tFNA自身的目标层分布。两层合计保留量范围为{hs.target_retention_ug_cm2.min():.4f}–{hs.target_retention_ug_cm2.max():.4f} μg/cm²。缺少对照载体的人体匹配参数，故此处仅评估tFNA迁移，未形成跨载体人体排名。

![人体迁移情景](../figures/fig11_human_transfer.png)

为检查参数可辨识性，固定五个Pₛ值分别校准D：

{table(hi,{"surface_P_cm_h":"假定表面P","D_cm2_h":"条件D","rmse":"形状RMSE","target_retention_ug_cm2":"两层保留"})}

相近的归一化拟合与不同绝对保留量可以同时出现，说明形状数据不能充分约束表面进入量。直接实验应补充分层CK绝对质量、donor剩余量和载体完整性。人体实际层厚、附属器差异可在获得参数依据后进入生理结构迁移。

## 7. 配对不确定性与敏感性

17维Latin hypercube抽样，共256组，随机种子20260827。同组四个系统共享SC、VE、真皮厚度及屏障因子，各系统D、K和Pₛ独立抽取。SC为10–20 μm、VE为60–120 μm、真皮为300–500 μm；屏障因子0.5–1.5，载体K乘子0.3–3，Pₛ为10⁻⁴–10⁻² cm/h。载体D范围：tFNA与脂质体为各自条件校准值的0.5–2倍，NLC为0.25–4倍；游离CK的D乘子为0.5–2、logP为5.2–6、Pₛ为0.03–0.30。厚度和logP为均匀抽样，其余所列正值范围为对数均匀。

主输出为两层合计保留量。中央95%区间描述指定情景分布，排名第一频率描述样本排序；二者均不是实验置信度或临床成功概率。跨条件迁移和边界结构情景单独呈现，未将这些不同来源人为混合为一个概率分布。

{ut}

{table(pair,{"first_system":"系统A","second_system":"系统B","median_difference_ug_cm2":"A−B中位差","lower_95_ug_cm2":"2.5%分位","upper_95_ug_cm2":"97.5%分位","probability_first_greater":"A>B频率"})}

各组相关性最高的三个输入如下。敏感性反映设定范围内的关联，参数对选择的影响还需结合持平图；非单调关系可能被相关系数压低。

{table(sens.groupby('system',sort=False).head(3),{"system":"系统","parameter":"输入","spearman_rho":"Spearman相关"},3)}

## 8. 持平边界与实验决策

tFNA有效D取基线0.05–4倍，Pₛ取10⁻⁴–10⁻² cm/h，分别设21个对数间隔点，共441个条件。NLC和脂质体保持各自基线。该范围是探索设计，并非统计可信区间。计算目标层保留差及零差等值线；对固定基线D下的Pₛ扫描全部符号变化区间，用求根方法确定交点。两层保留可能随D非单调变化，因而不能简单假设更快运输总会增加目标区存量。

![持平条件](../figures/fig12_decision_boundaries.png)

{table(roots,{"comparator":"固定对照","metric":"比较指标","surface_P_cm_h":"持平P cm/h","relative_to_baseline_P":"相对基线P","status":"范围内交点"})}

指标名target_retention、VE_mass、dermis_mass分别对应两层合计、VE与真皮保留；no_crossing_in_scanned_range表示扫描范围内未找到交点。具体数值依赖固定的对照参数、几何及零释放条件。

| 下一步测量 | 解决的未知量 | 对后续选择的用途 |
|---|---|---|
| 早期donor、皮肤与receiver的CK绝对质量 | 表面进入及总回收 | 约束Pₛ并定位持平区域 |
| VE与真皮分别定量，覆盖早期和24 h | 目标层分配与暴露 | 检验合计保留及空间偏向 |
| 载体标记、CK定量与结构完整性联合读数 | 完整结合态与释放货物区别 | 检验运输状态假设 |
| 匹配人皮条件，记录层厚并留出供体 | 跨条件迁移误差 | 校准后作独立预测检验 |

当实测约束的参数区域支持有竞争力的目标层保留，且装载和稳定性可行，可继续优先开展tFNA研究；当其主要落入对照更高的区域，应调整配方或并行验证对照。区间覆盖持平线时，优先测量能够收窄该区间的量。最低有效暴露量需由作用机制与实验依据制定，本模型没有人为设定药效通过线。

## 9. 数值验证与复现

数值检查通过{int(tests.passed.sum())}/{len(tests)}项，覆盖解析解、质量守恒、非负性、主指标网格收敛、矩阵指数与BDF一致性及游离CK经验式核对。决策分析检查通过{int(checks.passed.sum())}/{len(checks)}项，包含质量恒等式、迁移拟合诊断、条件网格物理范围与持平求根残差。拟合诊断反映计算行为，生物学有效性仍由相关实验验证。

在工作区运行 `python task1_delivery_model/run_all.py`。程序加载项目离线依赖，生成校准、基线、分层AUC、配对情景、人体迁移、边界情景、持平条件、12组PNG/SVG数值图及三份Markdown报告。结果表位于results/calibration、results/baseline、results/uncertainty与results/decision。源数据及证据矩阵位于data/processed。

任务二接口输出三类载体在SC、VE和真皮的结合态当量时间序列，附零释放与基线参数标识。该接口代表本报告条件下的模型输入，后续细胞或药效模型需另行验证，跨条件不确定性不能被视为已经消除。

## 10. 参考文献

{REFERENCES}
"""
    from .full_report import compose_full_report
    full=compose_full_report(full,root,table,FIGURES)
    from .brief_report import compose_brief_report
    brief=compose_brief_report(root)
    from .graphical_report import compose_graphical_report
    graph=compose_graphical_report(root,table)
    output=root/"output"
    for suffix,text in [("完整",full),("简要",brief),("图解",graph)]:
        if only is None or only==suffix:
            (output/f"任务一_递送建模横向比较{suffix}报告.md").write_text(text,encoding="utf-8")
    if only is not None:
        return
    (root/"README.md").write_text(f"""# 任务一：目标皮肤层递送潜力评估

主指标：24 h活性表皮与浅真皮合计保留量。统一剂量1 μg/cm²，有限donor，三层几何15/85/400 μm，载体释放率0。

{conclusion}

运行 `python task1_delivery_model/run_all.py` 可生成条件校准、基线、分层AUC、256组配对情景、人体辅助迁移、边界条件情景、持平条件、12组数值图和三份Markdown报告。依赖从 `.python_packages` 加载。

- [完整报告](output/任务一_递送建模横向比较完整报告.md)
- [简要报告](output/任务一_递送建模横向比较简要报告.md)
- [图解报告](output/任务一_递送建模横向比较图解报告.md)

人体辅助曲线属于条件校准；参数情景频率不能解释为真实成功概率。`results/decision` 保存边界一致性、人体迁移、参数可辨识性与选择条件。`results/task2_interface.csv` 是基线条件下的三类载体结合态输入。
""",encoding="utf-8")
