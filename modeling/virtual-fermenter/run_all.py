# -*- coding: utf-8 -*-
"""一键复现核心数值分析：虚拟发酵罐 v2（锚定 + 网格 + 动态图）与 BO + 帕累托前沿。

用法：在 virtual_fermenter_model/ 下执行  python run_all.py
输出：dbtl_round1_round2.png、bo_pareto_v2.png 写入 src/ 目录
     （figures/ 保存的是整理时的原始输出，可先复制一份再运行）。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')

STEPS = ['virtual_fermenter_v2.py', 'bo_pareto_v2.py']


def main():
    for name in STEPS:
        script = os.path.join(SRC, name)
        print('=' * 64)
        print('RUN:', name)
        print('=' * 64)
        subprocess.run([sys.executable, script], cwd=SRC, check=True)
    print('\n完成。输出图见 src/ 目录。')


if __name__ == '__main__':
    main()
