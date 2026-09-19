"""
iGEM 2026 JLU-NBBMS — 虚拟发酵罐 v2：贝叶斯优化(BO) + 帕累托前沿
依赖 virtual_fermenter_v2.CKSimulatorV2（单点锚定 round-1=30 mg/L）
输出: 控制台结果 + bo_pareto_v2.png
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from skopt import gp_minimize
from skopt.space import Real
from virtual_fermenter_v2 import CKSimulatorV2, COLOR_DARK, COLOR_LIGHT

sim = CKSimulatorV2()
P_r1 = 30.0
sim.anchor(P_r1)

# ============ 1. BO：最大化 CK（3 变量 T / S0 / 时间）============
space = [Real(24.0, 34.0, name='T'),
         Real(20.0, 40.0, name='S0'),
         Real(48.0, 120.0, name='time')]


def neg_CK(x):
    T, S0, tt = map(float, x)
    _, _, _, P = sim.simulate(T, S0, tt)
    return -P[-1]


res = gp_minimize(neg_CK, space, n_calls=80, n_initial_points=20, random_state=0)
T_opt, S0_opt, t_opt = res.x
CK_opt = -res.fun

print("=" * 62)
print("BO 优化（最大化 CK，变量 T/S0/time）")
print("=" * 62)
print(f"全局最优: T={T_opt:.1f}°C, S0={S0_opt:.1f} g/L, t={t_opt:.1f} h")
print(f"         → CK = {CK_opt:.1f} mg/L ({CK_opt / P_r1:.1f}×)")

# ============ 2. 网格 + 帕累托前沿 ============
Tg = np.arange(26.0, 31.5, 0.5)
S0g = np.arange(20.0, 42.0, 2.0)
tg = np.arange(48.0, 121.0, 6.0)
rows = []
for T in Tg:
    for S0 in S0g:
        for tt in tg:
            _, _, _, P = sim.simulate(T, S0, tt)
            rows.append((P[-1], tt, S0, T))
rows = np.array(rows)
CK, time, S0v, Tv = rows[:, 0], rows[:, 1], rows[:, 2], rows[:, 3]


def pareto_mask(c1, c2):
    """双目标非支配排序：c1 最大化、c2 最小化"""
    n = len(c1)
    keep = np.ones(n, dtype=bool)
    order = np.argsort(-c1)
    for i in order:
        if not keep[i]:
            continue
        for j in order:
            if j == i or not keep[j]:
                continue
            if c1[j] <= c1[i] and c2[j] >= c2[i] and (c1[j] < c1[i] or c2[j] > c2[i]):
                keep[j] = False
    return keep


front_t = rows[pareto_mask(CK, time)]
front_t = front_t[np.argsort(front_t[:, 1])]  # 按时间排序
front_s = rows[pareto_mask(CK, S0v)]
front_s = front_s[np.argsort(front_s[:, 2])]  # 按 S0 排序

# 推荐 round-2：温度不动(30°C)，主杠杆=时间+葡萄糖，fold 最接近 2.5×（2~3× 中位）
# 与 virtual_fermenter_v2.py 的推荐逻辑一致（T=30 固定）
target = 2.5 * P_r1
m30 = np.isclose(Tv, 30.0)
rec = rows[m30][np.argmin(np.abs(CK[m30] - target))]
print(f"\n推荐 round-2 (T=30°C, 最接近 2.5×): T={rec[3]:.1f}°C, S0={rec[2]:.0f} g/L, t={rec[1]:.0f} h")
print(f"         → CK = {rec[0]:.1f} mg/L ({rec[0] / P_r1:.1f}×)")

# ============ 3. 图 ============
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

ax = axes[0]
ax.scatter(time, CK, s=8, color='#d9d9d9', alpha=0.4, label='all grid points')
ax.plot(front_t[:, 1], front_t[:, 0], '-o', color=COLOR_DARK, lw=2, ms=4,
        label='Pareto front (max CK, min time)')
ax.scatter([t_opt], [CK_opt], marker='*', s=240, color=COLOR_DARK, zorder=5,
           label=f'BO optimum ({CK_opt:.0f} mg/L)')
ax.scatter([rec[1]], [rec[0]], marker='D', s=90, color=COLOR_LIGHT, zorder=5,
           label=f'recommended ({rec[0]:.0f} mg/L, {rec[0] / P_r1:.1f}×)')
ax.axhline(50, color='gray', ls=':', lw=1, alpha=0.6)
ax.axhline(100, color='gray', ls=':', lw=1, alpha=0.6)
ax.set_xlabel('Fermentation time (h)')
ax.set_ylabel('CK titer (mg/L)')
ax.set_title('Pareto front: CK vs time')
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

ax = axes[1]
ax.scatter(S0v, CK, s=8, color='#d9d9d9', alpha=0.4, label='all grid points')
ax.plot(front_s[:, 2], front_s[:, 0], '-o', color=COLOR_DARK, lw=2, ms=4,
        label='Pareto front (max CK, min S0)')
ax.scatter([S0_opt], [CK_opt], marker='*', s=240, color=COLOR_DARK, zorder=5,
           label=f'BO optimum ({CK_opt:.0f} mg/L)')
ax.scatter([rec[2]], [rec[0]], marker='D', s=90, color=COLOR_LIGHT, zorder=5,
           label=f'recommended ({rec[0]:.0f} mg/L)')
ax.set_xlabel('Initial glucose S0 (g/L)')
ax.set_ylabel('CK titer (mg/L)')
ax.set_title('Pareto front: CK vs glucose')
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

plt.suptitle('BO optimization + Pareto front (virtual fermenter v2)', fontsize=13, fontweight='bold', color=COLOR_DARK)
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.savefig('bo_pareto_v2.png', dpi=150, bbox_inches='tight')
print("\n[OK] 图已保存: bo_pareto_v2.png")
