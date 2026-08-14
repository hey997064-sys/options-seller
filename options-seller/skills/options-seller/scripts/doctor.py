#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""期权卖方报告 · 环境自检（doctor）。

逐项检查依赖，任何一项不过即给出人话修复指引并退出非零。
预检不过不进主流程——避免"跑到一半才失败"。

用法: python3 doctor.py
"""
import json
import shutil
import subprocess
import sys

PROBE = "AAPL.US"   # 自检探针标的：期权链最全，几乎不会下架


def run(*args, timeout=45):
    p = subprocess.run(["longbridge", *args, "--format", "json"],
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return json.loads(p.stdout)


def check(label, fn, fix):
    try:
        detail = fn() or ""
        print(f"  ✓ {label} {detail}")
        return True
    except Exception as e:
        print(f"  ✗ {label}")
        print(f"    问题: {str(e)[:160]}")
        print(f"    修复: {fix}")
        return False


def c_cli():
    if not shutil.which("longbridge"):
        raise RuntimeError("PATH 中没有 longbridge 命令")


def c_auth():
    q = run("quote", PROBE)
    return f"(现价 ${q[0]['last']})"


def c_chain():
    exps = run("option", "chain", PROBE)
    if not exps:
        raise RuntimeError("期权链为空")
    return f"({len(exps)} 个到期日)"


def c_option_quote():
    exps = [r["expiry_date"] for r in run("option", "chain", PROBE)]
    exp = exps[min(2, len(exps) - 1)]
    chain = run("option", "chain", PROBE, "--date", exp)
    spot = float(run("quote", PROBE)[0]["last"])
    k = min((float(r["strike"]) for r in chain), key=lambda x: abs(x - spot))
    sym = f"AAPL{exp[2:4]}{exp[5:7]}{exp[8:10]}C{int(k * 1000)}.US"
    q = run("option", "quote", sym)
    if not q or not q[0].get("open_interest"):
        raise RuntimeError("合约报价为空——账户很可能没有美股期权行情权限")
    return f"(试拉 {sym} OK)"


def main():
    print("期权卖方报告 · 环境自检")
    ok = True
    ok &= check("Python 版本 ≥ 3.9", lambda: None if sys.version_info >= (3, 9) else (_ for _ in ()).throw(
        RuntimeError(f"当前 {sys.version.split()[0]}")), "安装 Python 3.9+（macOS: xcode-select --install 或 brew install python3）")
    ok &= check("longbridge CLI 已安装", c_cli,
                "安装 CLI: https://longbridge.com/cli （或参考插件 README）")
    if not ok:
        sys.exit(1)
    ok &= check("CLI 登录态有效（股票行情）", c_auth,
                "运行 `longbridge login` 重新登录长桥账户")
    if not ok:
        sys.exit(1)
    ok &= check("期权链可访问", c_chain,
                "该账户看不到期权链，请确认长桥账户已开通期权交易/行情")
    ok &= check("美股期权行情权限（合约级报价）", c_option_quote,
                "在长桥 App 内开通美股期权行情（行情商店），本工具无法代开")
    if not ok:
        sys.exit(1)
    print("全部通过，可以出报告。")


if __name__ == "__main__":
    main()
