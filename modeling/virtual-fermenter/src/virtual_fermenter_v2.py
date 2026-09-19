"""
iGEM 2026 JLU-NBBMS — 虚拟发酵罐 v2（DBTL 版）
3 态 ODE：葡萄糖(S) → 生物量(X) → CK(P)，PPD 中间体经拟稳态塌缩进 k_eff
建模方法：文献参数化 + 单点锚定 + 相对优化

用法: python virtual_fermenter_v2.py
输出: 控制台结果 + dbtl_round1_round2.png
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt

COLOR_DARK = '#7E0909'
COLOR_LIGHT = '#F9A48B'


class CKSimulatorV2:
    """3 态：X (gDCW/L)、S (g/L)、P (mg/L)。X/S 与 P 解耦。"""

    def __init__(self):
        # --- A 档：文献固定值 ---
        self.mu_max  = 0.40   # h^-1 最大比生长速率
        self.K_S     = 0.5    # g/L 葡萄糖半饱和常数
        self.Y_XS    = 0.50   # g/g 菌体对葡萄糖得率
        self.m_s     = 0.02   # g/(g·h) 维持系数
        self.X0      = 0.05   # g/L 初始菌量（单菌落小量）
        self.T_opt_g = 30.0   # °C 生长最适温度（= 湿实验温度）
        self.sig_T_g = 5.0    # °C 生长温度宽度
        # --- A 档：文献值 ---
        self.T_opt_p = 28.0   # °C 生产最适温度（DoE 优化 28°C, pubmed 39181198；UGTPg1 体外 35°C, BRENDA）
        self.sig_T_p = 4.0    # °C 生产温度宽度（文献未给，估计值）
        # --- B 档：单点锚定 ---
        self.k_eff   = None   # mg/(g·h)，由 round-1 CK 反解

    def _gauss(self, T, T_opt, sig):
        return np.exp(-(T - T_opt) ** 2 / (2 * sig ** 2))

    def _cumtrapz(self, y, dt):
        """梯形法累计积分"""
        c = np.zeros_like(y)
        for i in range(1, len(y)):
            c[i] = c[i - 1] + 0.5 * (y[i - 1] + y[i]) * dt
        return c

    def _integrate_growth(self, T, S0, t_total, dt=0.05):
        """积分 X、S（与 P 解耦）；X_max 由底物量守恒 = Y_XS·S0"""
        n = int(round(t_total / dt))
        X = np.zeros(n + 1)
        S = np.zeros(n + 1)
        X[0], S[0] = self.X0, S0
        X_max = self.Y_XS * S0  # 底物限定的菌体上限（质量守恒）
        fTg = self._gauss(T, self.T_opt_g, self.sig_T_g)
        for i in range(n):
            mu = self.mu_max * fTg * (S[i] / (self.K_S + S[i])) * (1 - X[i] / X_max)
            dX = mu * X[i]
            dS = -(1 / self.Y_XS) * dX - self.m_s * X[i]
            X[i + 1] = X[i] + dX * dt
            S[i + 1] = max(0.0, S[i] + dS * dt)
        return np.arange(n + 1) * dt, X, S

    def anchor(self, P_round1, T=30.0, S0=20.0, t1=72.0):
        """单点锚定：k_eff = P_round1 / (fTp(T) · ∫X dt)"""
        t, X, _ = self._integrate_growth(T, S0, t1)
        integral_X = self._cumtrapz(X, t[1] - t[0])[-1]
        fTp = self._gauss(T, self.T_opt_p, self.sig_T_p)
        self.k_eff = P_round1 / (fTp * integral_X)
        return self.k_eff

    def simulate(self, T, S0, t_total, dt=0.05):
        """完整 3 态模拟；返回 t, X, S, P"""
        t, X, S = self._integrate_growth(T, S0, t_total, dt)
        fTp = self._gauss(T, self.T_opt_p, self.sig_T_p)
        P = self.k_eff * fTp * self._cumtrapz(X, dt)
        return t, X, S, P


def main():
    sim = CKSimulatorV2()

    # ---- 1. 单点锚定 round-1 = 30 mg/L ----
    P_r1 = 30.0
    k_eff = sim.anchor(P_r1)
    print("=" * 60)
    print("DBTL 虚拟发酵罐 v2 — 文献参数化 + 单点锚定")
    print("=" * 60)
    print(f"[锚定] round-1 CK = {P_r1:.0f} mg/L @ (T=30°C, S0=20 g/L, t=72h)")
    print(f"       → k_eff = {k_eff:.4f} mg/(g·h)  (落在 1e-2~1 目标量级)")

    # ---- 2. round-1 基线验证 ----
    t1, X1, S1, P1 = sim.simulate(30.0, 20.0, 72.0)
    print(f"[round-1] CK = {P1[-1]:.1f} mg/L, 生物量峰值 = {X1.max():.1f} g/L, 残糖 = {S1[-1]:.1f} g/L")

    # ---- 3. round-2 网格搜索（3 变量：T / S0 / 时间）----
    print("\n[Design] 3 变量网格搜索 ...")
    T_grid = np.arange(24.0, 35.0, 0.5)
    S0_grid = np.arange(20.0, 42.0, 2.0)
    t_grid = np.arange(48.0, 121.0, 6.0)
    best = None
    for T in T_grid:
        for S0 in S0_grid:
            for tt in t_grid:
                _, _, _, P = sim.simulate(T, S0, tt)
                val = P[-1]
                if best is None or val > best[0]:
                    best = (val, T, S0, tt)
    fold_best = best[0] / P_r1
    print(f"[理论上限] CK = {best[0]:.1f} mg/L  ({fold_best:.1f}×)  ← 参考上界，不采为 round-2")
    print(f"           条件: T={best[1]:.1f}°C, S0={best[2]:.0f} g/L, t={best[3]:.0f} h")
    print("           原因: T_opt^p 是待文献占位，S0=40 偏高，超出 50~100 目标区间")

    # ---- 4. 推荐 round-2（务实约束：T 不动=30°C，主杠杆=时间+葡萄糖）----
    # 2~3× 由"时间 72→96 h + 葡萄糖 20→36 g/L"驱动，与 T_opt^p 无关，最稳。
    print("\n[推荐 round-2] 温度不动(30°C)，取最接近 2.5×（2~3× 中位）的条件 ...")
    target = 2.5
    recommended = None
    for S0 in S0_grid:
        for tt in t_grid:
            _, _, _, P = sim.simulate(30.0, S0, tt)
            fold = P[-1] / P_r1
            if 2.0 <= fold <= 3.0:
                key = (abs(fold - target), S0, tt)  # 先接近 2.5×，再小 S0，再小 t
                if recommended is None or key < recommended[0]:
                    recommended = (key, fold, S0, tt, P[-1])
    if recommended:
        _, f_rec, S0_rec, t_rec, P_rec = recommended
        print(f"   CK = {P_rec:.1f} mg/L ({f_rec:.1f}×) @ T=30°C, S0={S0_rec:.0f} g/L, t={t_rec:.0f} h")
    else:
        f_rec, S0_rec, t_rec, P_rec = None, 20.0, 72.0, P_r1
        print("   （T=30 下无 2~3× 点）")

    # ---- 5. 画 round-1 vs round-2（用推荐条件）----
    T2, S0_2, t2 = 30.0, S0_rec, t_rec
    tA, XA, SA, PA = sim.simulate(30.0, 20.0, max(72.0, t2))
    tB, XB, SB, PB = sim.simulate(T2, S0_2, t2)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    ax = axes[0]
    ax.plot(tA, XA, color=COLOR_DARK, lw=2.2, label='round-1 biomass')
    ax.plot(tB, XB, color=COLOR_LIGHT, lw=2.2, label='round-2 biomass')
    ax.set_xlabel('Time (h)'); ax.set_ylabel('Biomass (g DCW/L)')
    ax.set_title('Biomass'); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(tA, SA, color=COLOR_DARK, lw=2.2, label='round-1 glucose')
    ax.plot(tB, SB, color=COLOR_LIGHT, lw=2.2, label='round-2 glucose')
    ax.set_xlabel('Time (h)'); ax.set_ylabel('Glucose (g/L)')
    ax.set_title('Glucose (model-predicted)'); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[2]
    ax.plot(tA, PA, color=COLOR_DARK, lw=2.5, label=f'round-1 ({PA[-1]:.0f} mg/L)')
    ax.plot(tB, PB, color=COLOR_LIGHT, lw=2.5, label=f'round-2 ({PB[-1]:.0f} mg/L)')
    ax.axhline(50, color='gray', ls=':', lw=1, alpha=0.7)
    ax.axhline(100, color='gray', ls=':', lw=1, alpha=0.7)
    ax.set_xlabel('Time (h)'); ax.set_ylabel('CK titer (mg/L)')
    ax.set_title(f'CK production (round-2 = {PB[-1]/PA[-1]:.1f}×)')
    ax.legend(); ax.grid(alpha=0.3)

    plt.suptitle('DBTL virtual fermenter v2 — round-1 vs round-2', fontsize=13,
                 fontweight='bold', color=COLOR_DARK)
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig('dbtl_round1_round2.png', dpi=150, bbox_inches='tight')
    print("\n[OK] 图已保存: dbtl_round1_round2.png")


if __name__ == '__main__':
    main()
