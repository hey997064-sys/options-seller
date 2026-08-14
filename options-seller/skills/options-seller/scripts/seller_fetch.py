#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""期权卖方报告 · 取数（分发版，纯标准库，自包含）。

用法:
    python3 seller_fetch.py NVDA [--today YYYY-MM-DD] [--allow-earnings] [--out seller_data.json]

流程: 到期日自选(贴 30/37/44 天) → 财报门 → 窗口链取数 → BS 定 delta → 双向三档选腿
      → 窗口 OI 墙 / PCR / Max Pain / IV / HV → 恒等式断言 → seller_data.json

退出码契约（SKILL.md 依此转述，非零禁止渲染报告）:
    0 成功 | 2 参数错误 | 3 无可用期权链或窗口内无到期日 | 4 行情获取失败
    5 财报落在持仓窗口内（拒跑，--allow-earnings 可越过） | 6 疑似无美股期权行情权限
"""
import argparse
import json
import math
import statistics
import subprocess
import sys
from datetime import date

R = 0.025                                    # BS 无风险利率，与 App delta 展示口径对账校准
TARGETS = [("稳健", 44), ("均衡", 37), ("进取", 30)]   # 档位 → 目标 DTE
DTE_MIN, DTE_MAX = 28, 46                    # 开仓窗（约 30–45 天，随周内滚动放宽到 28–46）
BANDS = [("稳健", 0.15, 0.25), ("均衡", 0.25, 0.35), ("进取", 0.35, 0.45)]
CHUNK = 40                                   # option quote 单次批量上限（保守值）


def die(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def cli(*args, timeout=90):
    """调用 longbridge CLI，失败即整体退出（用于必需数据）。"""
    try:
        p = subprocess.run(["longbridge", *args, "--format", "json"],
                           capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        die(4, "未找到 longbridge CLI。请先安装并登录（先跑 doctor.py 自检）")
    except subprocess.TimeoutExpired:
        die(4, f"行情请求超时: longbridge {' '.join(args)}")
    if p.returncode != 0:
        die(4, f"行情获取失败: longbridge {' '.join(args)}\n{p.stderr.strip()[:300]}")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        die(4, f"行情返回无法解析: longbridge {' '.join(args)}\n{p.stdout[:200]}")


def cli_soft(*args, timeout=90):
    """容错版：单块失败返回 None（用于合约报价分块，允许个别块丢失）。"""
    try:
        p = subprocess.run(["longbridge", *args, "--format", "json"],
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            return None
        return json.loads(p.stdout)
    except Exception:
        return None


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def npdf(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def bs(spot, k, t, iv, is_put):
    d1 = (math.log(spot / k) + (R + iv * iv / 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    delta = ncdf(d1) - (1 if is_put else 0)
    common = -spot * npdf(d1) * iv / (2 * math.sqrt(t))
    theta = (common + R * k * math.exp(-R * t) * ncdf(-d2)) / 365 if is_put \
        else (common - R * k * math.exp(-R * t) * ncdf(d2)) / 365
    return delta, theta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", help="美股标的，如 NVDA 或 NVDA.US")
    ap.add_argument("--today", default=None, help="覆盖当日日期（测试用）")
    ap.add_argument("--allow-earnings", action="store_true", help="财报在窗口内时仍继续（默认拒跑）")
    ap.add_argument("--out", default="seller_data.json")
    a = ap.parse_args()

    symbol = a.symbol.upper()
    if "." not in symbol:
        symbol += ".US"
    if not symbol.endswith(".US"):
        die(2, "仅支持美股标的（<CODE> 或 <CODE>.US）")
    code = symbol.split(".")[0]
    today = date.fromisoformat(a.today) if a.today else date.today()

    # ---- 现价 ----
    q = cli("quote", symbol)
    if not q:
        die(4, f"取不到 {symbol} 报价，请确认代码正确")
    spot = float(q[0]["last"])
    prev_close = float(q[0].get("prev_close") or 0) or None
    chg_pct = round((spot / prev_close - 1) * 100, 2) if prev_close else None

    # ---- 到期日自选：全部真实到期日里，给每档挑最贴目标 DTE 的一天 ----
    exp_rows = cli("option", "chain", symbol)
    all_exps = {}
    for r in exp_rows or []:
        e = r.get("expiry_date")
        if not e:
            continue
        dte = (date.fromisoformat(e) - today).days
        if DTE_MIN <= dte <= DTE_MAX:
            all_exps[e] = dte
    if not exp_rows:
        die(3, f"{symbol} 无可用期权链（该标的未上市期权，或账户无期权行情权限）")
    if not all_exps:
        die(3, f"{symbol} 在开仓窗（{DTE_MIN}–{DTE_MAX} 天）内没有到期日，本工具按 30–45 天开仓惯例筛选，暂无法出报告")
    band_exp = {name: min(all_exps, key=lambda e: (abs(all_exps[e] - t), e))
                for name, t in TARGETS}
    expiries = sorted(set(band_exp.values()))

    # ---- 财报门：窗口内有财报直接拒跑（期权卖方最忌财报夜，硬规则）----
    earnings_next = None
    cal = cli("finance-calendar", "report", "--symbol", symbol,
              "--start", str(today), "--end", max(expiries))
    events = []
    for day in (cal.get("list") or []):
        for info in (day.get("infos") or []):
            if code in str(info.get("counter_id", "")):
                events.append(day.get("date") or info.get("date"))
    if events:
        earnings_next = sorted(events)[0]
        if not a.allow_earnings:
            die(5, f"{code} 下次财报 {earnings_next} 落在持仓窗口内（最远到期 {max(expiries)}）。"
                   f"财报夜波动会击穿卖方策略，本工具默认拒绝出报告；"
                   f"如确要继续请加 --allow-earnings（报告将标注财报风险）")

    # ---- HV30：近 30 个交易日对数收益年化 ----
    ks = cli("kline", symbol, "--period", "day", "--count", "50")
    closes = [float(k["close"]) for k in ks][-31:]
    if len(closes) < 15:
        die(4, f"{symbol} 日 K 不足（{len(closes)} 根），无法计算 HV")
    rets = [math.log(closes[i + 1] / closes[i]) for i in range(len(closes) - 1)]
    hv_pct = round(statistics.stdev(rets) * math.sqrt(252) * 100, 1)

    # ---- 窗口链取数：OI 分布 + 候选腿池 + ATM IV ----
    oi_dist = {}            # strike -> [call_oi, put_oi]（窗口内到期日合计）
    oi_near = {}            # 最近到期日单日 OI（Max Pain 用）
    cands = []
    atm_iv = None
    near_exp = min(expiries, key=lambda e: all_exps[e])
    atm_exp = min(expiries, key=lambda e: abs(all_exps[e] - 30))
    failed_chunks = 0
    for exp in expiries:
        dte = all_exps[exp]
        chain = cli("option", "chain", symbol, "--date", exp)
        strikes = [float(r["strike"]) for r in chain
                   if 0.72 * spot <= float(r["strike"]) <= 1.30 * spot]
        if exp == atm_exp and chain:
            atm_row = min(chain, key=lambda r: abs(float(r["strike"]) - spot))
            raw = float(atm_row.get("put_iv") or 0)
            # 链返回的 IV 为小数（0.68）；防御性兼容百分数形态
            atm_iv = round(raw * 100, 1) if 0 < raw < 3 else (round(raw, 1) or None)
        yy, mm, dd = exp[2:4], exp[5:7], exp[8:10]
        syms = [(f"{code}{yy}{mm}{dd}{side}{int(k * 1000)}.US", k, side)
                for k in strikes for side in ("C", "P")]
        quotes = {}
        for i in range(0, len(syms), CHUNK):
            chunk = [s[0] for s in syms[i:i + CHUNK]]
            res = cli_soft("option", "quote", *chunk) or cli_soft("option", "quote", *chunk)  # 失败重试一次
            if res is None:
                failed_chunks += 1
                print(f"warn: 报价块失败已跳过 ({exp} {i}-{i+CHUNK})", file=sys.stderr)
                continue
            for qq in res:
                quotes[qq["symbol"]] = qq
        for sym, k, side in syms:
            qq = quotes.get(sym)
            if not qq:
                continue
            oi = int(qq["open_interest"])
            d = oi_dist.setdefault(k, [0, 0])
            d[0 if side == "C" else 1] += oi
            if exp == near_exp:
                dn = oi_near.setdefault(k, [0, 0])
                dn[0 if side == "C" else 1] += oi
            prem, iv = float(qq["last"]), float(qq["implied_volatility"])
            if prem < 0.05 or iv <= 0 or oi < 10:
                continue
            if (side == "P" and k > 0.995 * spot) or (side == "C" and k < 1.005 * spot):
                continue
            delta, theta = bs(spot, k, dte / 365, iv, side == "P")
            base = k if side == "P" else spot
            cands.append(dict(side=side, exp=exp, dte=dte, strike=k, prem=round(prem, 2),
                              oi=oi, iv=round(iv, 3), delta=round(delta, 3),
                              theta_contract=round(theta * 100, 1),
                              ret_period=round(prem / base, 4),
                              ann=round(prem / base * 365 / dte, 4),
                              prob_otm=round(1 - abs(delta), 4),
                              score=round((1 - abs(delta)) * (250 / (dte + 5)) * (prem / k), 4)))

    if not oi_dist:
        die(6, f"{symbol} 期权报价全部取不到——大概率是账户没有美股期权行情权限。"
               f"请在长桥 App 内开通美股期权行情后重试（可先跑 doctor.py 自检确认）")
    if failed_chunks:
        print(f"warn: 共 {failed_chunks} 个报价块失败，OI 分布可能不完整", file=sys.stderr)

    # ---- 双向三档选腿：档内评分取优 ----
    picks = {"P": [], "C": []}
    for side in ("P", "C"):
        for name, lo, hi in BANDS:
            band = [c for c in cands if c["side"] == side and c["exp"] == band_exp[name]
                    and lo <= abs(c["delta"]) < hi]
            if band:
                picks[side].append({**max(band, key=lambda c: c["score"]), "band": name})

    # ---- 窗口墙 + 墙外标注 ----
    call_walls = sorted(oi_dist, key=lambda k: -oi_dist[k][0])[:2]
    put_walls = sorted(oi_dist, key=lambda k: -oi_dist[k][1])[:2]
    cw = max(call_walls, key=lambda k: oi_dist[k][0])
    pw = max(put_walls, key=lambda k: oi_dist[k][1])
    for c in picks["P"]:
        c["beyond_wall"] = c["strike"] <= pw
    for c in picks["C"]:
        c["beyond_wall"] = c["strike"] >= cw

    # ---- 窗口 PCR / Max Pain（最近到期日口径）----
    put_sum = sum(v[1] for v in oi_dist.values())
    call_sum = sum(v[0] for v in oi_dist.values())
    pcr_oi = round(put_sum / call_sum, 3) if call_sum else None
    mp_strike = None
    if oi_near:
        strikes_n = sorted(oi_near)
        def pain(kk):
            return sum(v[0] * max(0.0, kk - s) + v[1] * max(0.0, s - kk)
                       for s, v in oi_near.items())
        mp_strike = min(strikes_n, key=pain)
    max_pain = dict(strike=mp_strike, expiry=near_exp,
                    distance_pct=round((mp_strike / spot - 1) * 100, 1) if mp_strike else None)

    # ---- 新闻原料（热点段由 AI 从这里选写，只取波动相关）----
    news_raw = cli_soft("news", symbol) or []
    news = [dict(title=n.get("title"), time=n.get("published_at") or n.get("time"))
            for n in news_raw[:8]]

    # ---- 断言层：恒等式守门（算法身份断言，破坏即停）----
    for side in picks.values():
        for c in side:
            assert abs(c["prob_otm"] + abs(c["delta"]) - 1) < 0.001, c
            assert abs(c["ann"] - c["ret_period"] * 365 / c["dte"]) < 0.001, c
            assert DTE_MIN <= c["dte"] <= DTE_MAX, c
    for c in picks["P"]:
        assert c["strike"] < spot
    for c in picks["C"]:
        assert c["strike"] > spot
    assert oi_dist[cw][0] == max(v[0] for v in oi_dist.values())
    assert oi_dist[pw][1] == max(v[1] for v in oi_dist.values())

    out = dict(asof=str(today), symbol=symbol, name=(cli_soft("static", symbol) or [{}])[0].get("name"),
               spot=spot, prev_close=prev_close, chg_pct=chg_pct,
               window=dict(expiries=expiries, band_exp=band_exp,
                           dte_min=min(all_exps[e] for e in expiries),
                           dte_max=max(all_exps[e] for e in expiries)),
               earnings=dict(checked=True, next_in_window=earnings_next),
               kpi=dict(atm_iv_pct=atm_iv, hv_pct=hv_pct,
                        iv_hv_spread_pp=round(atm_iv - hv_pct, 1) if atm_iv else None,
                        pcr_oi_window=pcr_oi, max_pain=max_pain),
               oi_dist={f"{k:g}": v for k, v in sorted(oi_dist.items())},
               call_walls=call_walls, put_walls=put_walls,
               puts=picks["P"], calls=picks["C"], news=news)
    with open(a.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"written {a.out}")
    print(f"spot={spot} ({chg_pct:+}% vs prev)" if chg_pct is not None else f"spot={spot}")
    print(f"expiries={expiries} call_wall={cw}(OI {oi_dist[cw][0]:,}) put_wall={pw}(OI {oi_dist[pw][1]:,}) "
          f"pcr={pcr_oi} iv={atm_iv} hv={hv_pct} max_pain={mp_strike}")
    for side_name, lst in (("PUT", picks["P"]), ("CALL", picks["C"])):
        for c in lst:
            print(f"  {side_name} {c['band']}: {c['exp']} K{c['strike']:g} prem={c['prem']}"
                  f" Δ={c['delta']} 年化={c['ann']:.1%} 墙外={c['beyond_wall']} OI={c['oi']}")


if __name__ == "__main__":
    main()
