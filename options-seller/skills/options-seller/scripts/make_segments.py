#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零 AI 降级：从 seller_data.json 按固定规则生成中性 segments.json（_source=auto）。

不解读新闻、不做判断，只陈述数据事实；渲染时段落标签自动显示「自动摘要」而非「AI 视角」。
用法: python3 make_segments.py [--data seller_data.json] [--out segments.json] [--force]
"""
import argparse
import json
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="seller_data.json")
ap.add_argument("--out", default="segments.json")
ap.add_argument("--force", action="store_true", help="覆盖已存在的 segments.json")
a = ap.parse_args()

if os.path.exists(a.out) and not a.force:
    print(f"{a.out} 已存在（可能是 AI 起草版），不覆盖。要重新生成请加 --force")
    sys.exit(0)

D = json.load(open(a.data))
K = D["kpi"]
spot, chg = D["spot"], D.get("chg_pct")
iv, hv, sp = K["atm_iv_pct"], K["hv_pct"], K["iv_hv_spread_pp"]
exp_labels = "、".join(f"{int(e[5:7])}/{int(e[8:10])}" for e in D["window"]["expiries"])
earn = D["earnings"].get("next_in_window")

tone_vol = "高波动" if (iv or 0) >= 60 else "中波动" if (iv or 0) >= 40 else "低波动"
thr = spot * 100
tone_thr = "低门槛" if thr < 20000 else "中门槛" if thr < 80000 else "高门槛"

chg_txt = f"较上一交易日{'上涨' if chg >= 0 else '下跌'} {abs(chg):g}%" if chg is not None else "涨跌幅数据缺失"
earn_txt = f"⚠ 下次财报 {earn} 落在持仓窗口内，财报夜波动风险显著。" if earn \
    else "筛选窗口内无财报事件。"

p_out = sum(1 for c in D["puts"] if c["beyond_wall"])
c_out = sum(1 for c in D["calls"] if c["beyond_wall"])

seg = {
 "_source": "auto",
 "series_title": "期权卖方报告：把波动率变成租金",
 "series_sub": "不猜方向，只做承诺：在你愿意成交的价格上把「承诺」卖出去，收下时间价值。",
 "sym_cn": D.get("name") or D["symbol"].split(".")[0],
 "sym_tone": f"{tone_vol} · {tone_thr}",
 "m1": f"{D['symbol'].split('.')[0]} 最新报 ${spot:g}，{chg_txt}。本期筛选窗口为 {exp_labels} 到期。{earn_txt}",
 "m2": "窗口内看涨持仓最厚的一档在 ${cw}（现价 +{cw_dist}%），看跌最厚的一档在 ${pw}（{pw_dist}%）。"
       "市场定价的 30 天波动预期为 {iv}%，近 30 个交易日实际波动为 {hv}%，两者之差 {spread}pp。"
       "Max Pain ${mp_strike} 位于现价 {mp_dist}% 处。以上为数据陈述，不构成方向判断。",
 "kpi_meaning": {
  "pcr": ">1 看跌持仓多，<1 看涨多",
  "iv": "市场预期的波动幅度，租金的基数",
  "hv": "近 30 个交易日的实际波动",
  "spread": "正 = 预期高于现实，负 = 低于",
  "max_pain": "距现价 {mp_dist}%",
  "walls": "上方 +{cw_dist}% / 下方 {pw_dist}%"
 },
 "m4_note": f"看跌示例 {p_out}/{len(D['puts'])} 条腿在主墙之外，看涨示例 {c_out}/{len(D['calls'])} 条在主墙之外；"
            f"「墙外」= 行权价越过对应主墙，离持仓最厚的防线更远。",
 "strat_put": "先收一笔权利金，承诺股价跌到行权价就买 100 股。没跌到，权利金归你；跌到了，按行权价买入。",
 "strat_call": "拿着 100 股，先收一笔权利金，承诺涨到行权价就卖出。没涨到，权利金归你，股票还在；涨到了，按行权价卖出。",
 "next_earnings": None
}
json.dump(seg, open(a.out, "w"), ensure_ascii=False, indent=1)
print(f"written {a.out} (_source=auto 自动摘要模式)")
