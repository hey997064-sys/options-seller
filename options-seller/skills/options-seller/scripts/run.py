#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键入口（无需任何 AI）：doctor → fetch → 自动文案 → 渲染 → 打开。

用法:
    python3 run.py NVDA [--allow-earnings] [--skip-doctor]

想要 AI 版文案：跑完本命令后，把本目录 PROMPT.md + seller_data.json 交给任意 AI 助手，
用它返回的 JSON 覆盖 segments.json，再执行:  python3 <本目录>/build_report.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def step(name, args, allow_fail=False):
    print(f"\n== {name}")
    p = subprocess.run([sys.executable, *args])
    if p.returncode != 0 and not allow_fail:
        sys.exit(p.returncode)
    return p.returncode


def main():
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        sys.exit(2)
    symbol = argv[0]
    flags = argv[1:]
    if "--skip-doctor" not in flags:
        step("环境自检", [os.path.join(HERE, "doctor.py")])
    fetch_args = [os.path.join(HERE, "seller_fetch.py"), symbol]
    if "--allow-earnings" in flags:
        fetch_args.append("--allow-earnings")
    step("取数", fetch_args)
    # --force：同目录重跑时文案随数据重建，避免"新数据+旧文案"自相矛盾（评测 P1-3）
    step("生成自动文案（零 AI 模式）", [os.path.join(HERE, "make_segments.py"), "--force"])
    step("渲染", [os.path.join(HERE, "build_report.py")])
    import glob
    outs = sorted(glob.glob("期权卖方报告-*.html"), key=os.path.getmtime)
    if outs:
        print(f"\n完成: {outs[-1]}")
        if "--no-open" in flags:
            pass
        elif sys.platform == "darwin":
            subprocess.run(["open", outs[-1]])
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", outs[-1]], stderr=subprocess.DEVNULL)
        print("提示：想要 AI 撰写的热点与定调段，把 PROMPT.md + seller_data.json 交给任意 AI 助手，"
              "用返回的 JSON 覆盖 segments.json 后重跑 build_report.py")


if __name__ == "__main__":
    main()
