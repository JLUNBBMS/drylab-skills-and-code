# -*- coding: utf-8 -*-
"""
iGEM 2026 JLU-NBBMS — 工业建模 wiki 配图（英文）
生成 4 张新图：
  fig1_dbtl_cycle.png        DBTL 循环流程图
  fig2_pathway.png           通路图 (glucose -> PPD -> CK)
  fig3_model_schematic.png   3 态模型结构图
  fig4_temperature_response.png  生长 vs 生产温度响应
风格统一：队色 COLOR_DARK=#7E0909, COLOR_LIGHT=#F9A48B
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['font.family'] = ['DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

DARK = '#7E0909'
LIGHT = '#F9A48B'
GRAY = '#666666'
LIGHTGRAY = '#E8E8E8'


def box(ax, x, y, w, h, text, fc='white', ec=DARK, fs=10, weight='normal', sub=None):
    p = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.08',
                       linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=2)
    ax.add_patch(p)
    if sub:
        ax.text(x + w/2, y + h*0.62, text, ha='center', va='center',
                fontsize=fs, weight=weight, color='black', zorder=3)
        ax.text(x + w/2, y + h*0.30, sub, ha='center', va='center',
                fontsize=fs-2.5, color=GRAY, zorder=3)
    else:
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=fs, weight=weight, color='black', zorder=3)


def arrow(ax, x1, y1, x2, y2, color=DARK, style='-|>', ls='-', lw=1.8, connectionstyle=None):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                        linewidth=lw, color=color, linestyle=ls, zorder=2,
                        connectionstyle=connectionstyle)
    ax.add_patch(a)


# ============ Figure 1: DBTL cycle ============
def fig_dbtl_cycle():
    fig, ax = plt.subplots(figsize=(11, 5.0))
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.0)
    ax.axis('off')

    bw, bh, y = 2.0, 1.9, 1.5
    xs = [0.3, 3.1, 5.9, 8.7]
    box(ax, xs[0], y, bw, bh, 'Build / Test', sub='wet round-1\n30 mg/L (anchor)')
    box(ax, xs[1], y, bw, bh, 'Learn', sub='dry: literature\n+ anchor k_eff')
    box(ax, xs[2], y, bw, bh, 'Design', sub='dry: BO + Pareto\n\u2192 round-2 conditions')
    box(ax, xs[3], y, bw, bh, 'Test', sub='wet round-2\n75 mg/L (2.5\u00d7)')

    # forward arrows between adjacent boxes
    for i in range(3):
        arrow(ax, xs[i] + bw, y + bh / 2, xs[i + 1], y + bh / 2)

    # dashed return arrow: Test -> Learn (iteration), curving below
    arrow(ax, xs[3] + bw / 2, y, xs[1] + bw / 2, y, color=GRAY, style='-|>',
          ls='--', lw=1.5, connectionstyle='arc3,rad=-0.22')
    ax.text((xs[3] + xs[1]) / 2 + bw / 2, 0.55, 'iterate', fontsize=9,
            color=GRAY, ha='center')

    ax.text(5.5, 4.6, 'DBTL cycle with the virtual-fermenter model',
            ha='center', fontsize=12.5, weight='bold', color=DARK)
    plt.tight_layout()
    plt.savefig('fig1_dbtl_cycle.png', dpi=150, bbox_inches='tight')
    plt.close()


# ============ Figure 2: pathway ============
def fig_pathway():
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 5)
    ax.axis('off')

    box(ax, 0.5, 1.8, 1.9, 1.4, 'Glucose (S)', fc='#F7F2EA')
    box(ax, 3.2, 3.3, 2.1, 1.4, 'Biomass (X)', fc='#F7F2EA')
    box(ax, 3.2, 0.3, 2.1, 1.4, 'PPD (I)', sub='internal', fc='#F2F2F2', ec=GRAY)
    box(ax, 7.6, 1.8, 2.0, 1.4, 'CK (P)', fc=LIGHT, ec=DARK)

    arrow(ax, 2.4, 2.5, 3.2, 3.6)
    ax.text(2.3, 3.3, 'growth', fontsize=9, color=DARK, ha='center')
    arrow(ax, 2.4, 2.5, 3.2, 1.2)
    ax.text(2.3, 1.4, 'MVA / terpene\npathway', fontsize=8.5, color=DARK, ha='center')
    arrow(ax, 5.3, 1.0, 7.6, 1.7)
    ax.text(6.4, 1.05, 'UGTPg1', fontsize=9, color=DARK, ha='center')
    # biomass -> CK (production proportional to X)
    arrow(ax, 5.3, 4.0, 7.9, 2.6, color=GRAY, style='-|>', ls='--', lw=1.6,
          connectionstyle='arc3,rad=-0.25')
    ax.text(5.4, 4.5, 'production \u221d X', fontsize=9, color=GRAY, ha='center')

    ax.text(5.0, 4.85, 'CK biosynthetic pathway in engineered S. cerevisiae',
            ha='center', fontsize=12, weight='bold', color=DARK)
    plt.tight_layout()
    plt.savefig('fig2_pathway.png', dpi=150, bbox_inches='tight')
    plt.close()


# ============ Figure 3: model schematic ============
def fig_model_schematic():
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 5.2)
    ax.axis('off')

    box(ax, 0.4, 1.7, 2.2, 1.6, 'S', sub='glucose (g/L)', fc='#F7F2EA')
    box(ax, 3.9, 1.7, 2.2, 1.6, 'X', sub='biomass (gDCW/L)', fc='#F7F2EA')
    box(ax, 7.4, 1.7, 2.2, 1.6, 'P', sub='CK (mg/L)', fc=LIGHT, ec=DARK)

    # S -> X growth
    arrow(ax, 2.6, 2.5, 3.9, 2.5)
    ax.text(3.25, 2.75, 'growth\nMonod\u2013Logistic', fontsize=8, ha='center', color=DARK)
    # X -> P production, with lumped PPD
    arrow(ax, 6.1, 2.5, 7.4, 2.5)
    ax.text(6.75, 2.78, 'dP/dt = k_eff \u00b7 f_T^p \u00b7 X', fontsize=8.5, ha='center', color=DARK)
    # PPD shaded box along the X->P arrow
    p = FancyBboxPatch((5.9, 0.5), 1.5, 1.0, boxstyle='round,pad=0.02,rounding_size=0.08',
                       linewidth=1.2, edgecolor=GRAY, facecolor='#EDEDED', linestyle='--', zorder=2)
    ax.add_patch(p)
    ax.text(6.65, 1.0, 'PPD (I)\nlumped', fontsize=8, ha='center', va='center', color=GRAY, zorder=3)
    arrow(ax, 6.65, 1.5, 6.65, 2.1, color=GRAY, style='-|>', ls=':', lw=1.2)

    ax.text(5.0, 4.9, 'Three-state model (PPD absorbed into k_eff)',
            ha='center', fontsize=12, weight='bold', color=DARK)
    plt.tight_layout()
    plt.savefig('fig3_model_schematic.png', dpi=150, bbox_inches='tight')
    plt.close()


# ============ Figure 4: temperature response ============
def fig_temperature():
    T = np.linspace(20, 38, 400)
    fg = np.exp(-(T - 30) ** 2 / (2 * 5 ** 2))
    fp = np.exp(-(T - 28) ** 2 / (2 * 4 ** 2))
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.plot(T, fg, color=DARK, lw=2.4, label='growth  f_T^g (opt 30 \u00b0C)')
    ax.plot(T, fp, color=LIGHT, lw=2.4, label='production  f_T^p (opt 28 \u00b0C)')
    ax.axvline(30, color=DARK, ls=':', lw=1, alpha=0.7)
    ax.axvline(28, color=LIGHT, ls=':', lw=1, alpha=0.7)
    ax.annotate('at 30 \u00b0C:\nf_T^p \u2248 0.88', xy=(30, fp[np.argmin(abs(T-30))]),
                xytext=(31.5, 0.55), fontsize=9, color='black',
                arrowprops=dict(arrowstyle='->', color=GRAY, lw=1))
    ax.set_xlabel('Temperature (\u00b0C)')
    ax.set_ylabel('activity factor (0\u20131)')
    ax.set_title('Growth vs production have different temperature optima',
                 fontsize=11.5, weight='bold', color=DARK)
    ax.set_ylim(0, 1.08)
    ax.legend(fontsize=9, frameon=False)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('fig4_temperature_response.png', dpi=150, bbox_inches='tight')
    plt.close()


if __name__ == '__main__':
    fig_dbtl_cycle()
    fig_pathway()
    fig_model_schematic()
    fig_temperature()
    print('OK -> fig1_dbtl_cycle.png, fig2_pathway.png, fig3_model_schematic.png, fig4_temperature_response.png')
