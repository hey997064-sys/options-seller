#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""期权卖方报告 · 渲染（分发版）。seller_data.json + segments.json → 双页 A4 品牌 HTML。

用法: python3 build_report.py [--data seller_data.json] [--segments segments.json]
输出: 期权卖方报告-<CODE>-<日期>.html（当前目录）
断言失败 = 数据被破坏，退出非零，禁止出报告。
"""
import argparse
import json
import math

ap = argparse.ArgumentParser(description="从当前目录读 seller_data.json + segments.json 渲染报告")
ap.add_argument("--data", default="seller_data.json")
ap.add_argument("--segments", default="segments.json")
args = ap.parse_args()

D = json.load(open(args.data))
CODE = D["symbol"].split(".")[0]
KPI = D["kpi"]
MP = KPI["max_pain"]
SPOT = D["spot"]
CW = max(D["call_walls"], key=lambda k: D["oi_dist"][f"{k:g}"][0])
PW = max(D["put_walls"], key=lambda k: D["oi_dist"][f"{k:g}"][1])
EXPS = D["window"]["expiries"]
EXP_LABELS = "、".join(f"{int(e[5:7])}/{int(e[8:10])}" for e in EXPS)

# ============ 结论/文案层：全部来自 segments.json（AI 起草，人工可点击改）============
_iv, _hv, _sp = KPI["atm_iv_pct"], KPI["hv_pct"], KPI["iv_hv_spread_pp"]
PLACEHOLDERS = dict(
    spot=f"{SPOT:g}", cw=f"{CW:g}", pw=f"{PW:g}",
    cw_dist=f"{(CW / SPOT - 1) * 100:.1f}", pw_dist=f"{(PW / SPOT - 1) * 100:.1f}",
    mp_strike=f"{MP['strike']:g}" if MP.get("strike") else "—",
    mp_dist=f"{MP['distance_pct']:+.1f}" if MP.get("distance_pct") is not None else "—",
    iv=f"{_iv:.1f}" if _iv else "—", hv=f"{_hv:.1f}", spread=f"{_sp:+.1f}" if _sp is not None else "—",
)


def fill(v):
    if isinstance(v, str):
        return v.format(**PLACEHOLDERS)
    if isinstance(v, dict):
        return {k: fill(x) for k, x in v.items()}
    return v


SEGMENTS = {k: fill(v) for k, v in json.load(open(args.segments)).items() if k != "_readme"}
NEXT_EARNINGS = SEGMENTS.get("next_earnings") or (
    f"{D['earnings']['next_in_window']} ⚠ 窗口内" if D["earnings"].get("next_in_window") else "窗口外")
# ============================================================================

BAND_DESC = {"稳健": "Δ≈0.2", "均衡": "Δ≈0.3", "进取": "Δ≈0.4"}


def fmt_oi_wan(n):
    return f"{n / 10000:.1f}万" if n >= 10000 else f"{n:,}"


def fmt_contract(c):
    e = c["exp"]
    return f"{CODE} {e[2:4]}{e[5:7]}{e[8:10]} {c['strike']:g}{c['side']}"


def leg_rows(legs, cls):
    rows = []
    for c in legs:
        badge = '<span class="wallbadge">墙外</span>' if c["beyond_wall"] else '<span class="wallbadge in">墙内</span>'
        rows.append(f"""
      <div class="row">
        <div class="c1"><div class="name">{fmt_contract(c)} {badge}</div>
          <div class="sub"><span class="tag">{c['band']} {BAND_DESC[c['band']]}</span>{c['dte']} 天 · OI {c['oi']:,} · theta ${-c['theta_contract']:.1f}/日</div></div>
        <div class="c2">
          <div class="kv"><span>权利金</span><b>${c['prem'] * 100:,.0f}/张</b></div>
          <div class="kv"><span>期内回报</span><b>+{c['ret_period'] * 100:.2f}%</b></div>
          <div class="kv"><span>价外概率</span><b>{c['prob_otm'] * 100:.0f}%</b></div>
        </div>
        <div class="c3 {cls}">+{c['ann'] * 100:.1f}%<small>年化回报率*</small></div>
      </div>""")
    return "".join(rows)


def nice_step(span, target=6):
    """轴刻度步长：从 1-2-5 序列里选出使刻度数接近 target 的一档（$3 到 $8000 的标的都能画）。"""
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def oi_chart():
    oi = {float(k): v for k, v in D["oi_dist"].items()}
    lo, hi = min(oi) * 0.99, max(oi) * 1.01
    W, BASE, HMAX = 700, 104, 64
    def x(p):
        return 44 + (p - lo) / (hi - lo) * (W - 88)
    mx = max(max(v) for v in oi.values())
    bw = min(6.8, max(2.4, (W - 88) / max(1, len(oi)) * 0.45))
    parts = []
    for k, (c_oi, p_oi) in sorted(oi.items()):
        cx = x(k)
        if c_oi:
            parts.append(f'<rect x="{cx - bw / 2:.1f}" y="{BASE - c_oi / mx * HMAX:.1f}" width="{bw:.1f}" height="{c_oi / mx * HMAX:.1f}" rx="1.5" fill="#FC5200" opacity="0.85"/>')
        if p_oi:
            parts.append(f'<rect x="{cx - bw / 2:.1f}" y="{BASE + 2}" width="{bw:.1f}" height="{p_oi / mx * HMAX:.1f}" rx="1.5" fill="#00B8B8" opacity="0.85"/>')
    parts.append(f'<line x1="40" y1="{BASE}" x2="{W - 40}" y2="{BASE}" stroke="#DDDDDF" stroke-width="1"/>')
    step = nice_step(hi - lo)
    t = math.ceil(lo / step) * step
    while t < hi:
        parts.append(f'<text x="{x(t):.0f}" y="{BASE + HMAX + 16}" text-anchor="middle" font-size="9" fill="#B0B4B8">{t:g}</text>')
        t += step
    parts.append(f'<line x1="40" y1="{BASE + HMAX + 24}" x2="{W - 40}" y2="{BASE + HMAX + 24}" stroke="#EEEEEF" stroke-width="1"/>')
    sx = x(SPOT)
    parts.append(f'<line x1="{sx:.0f}" y1="16" x2="{sx:.0f}" y2="{BASE + HMAX + 4}" stroke="rgba(0,0,0,0.85)" stroke-width="1.5" stroke-dasharray="3 2"/>')
    parts.append(f'<text x="{sx:.0f}" y="12" text-anchor="middle" font-size="10.5" font-weight="700" fill="rgba(0,0,0,0.85)">现价 {SPOT:g}</text>')
    cw_h = oi[CW][0] / mx * HMAX
    parts.append(f'<text x="{x(CW):.0f}" y="{BASE - cw_h - 8:.0f}" text-anchor="middle" font-size="10" font-weight="700" fill="#C24000">Call 主墙 ${CW:g} · {fmt_oi_wan(oi[CW][0])}</text>')
    pw_h = oi[PW][1] / mx * HMAX
    parts.append(f'<text x="{x(PW):.0f}" y="{BASE + pw_h + 16:.0f}" text-anchor="middle" font-size="10" font-weight="700" fill="#008080">Put 主墙 ${PW:g} · {fmt_oi_wan(oi[PW][1])}</text>')
    for c in D["puts"] + D["calls"]:
        cx = x(c["strike"])
        col = "#008080" if c["side"] == "P" else "#C24000"
        parts.append(f'<path d="M {cx - 4} {BASE + HMAX + 43} L {cx + 4} {BASE + HMAX + 43} L {cx} {BASE + HMAX + 36} Z" fill="{col}"/>')
        parts.append(f'<text x="{cx:.0f}" y="{BASE + HMAX + 55}" text-anchor="middle" font-size="8.5" fill="{col}">{c["strike"]:g}{c["side"]}</text>')
    parts.append(f'<text x="44" y="{BASE + HMAX + 47}" font-size="8.5" fill="#82888D">示例合约 ▾</text>')
    parts.append('<rect x="44" y="20" width="9" height="9" rx="2" fill="#FC5200" opacity="0.85"/><text x="57" y="28" font-size="9" fill="rgba(0,0,0,0.55)">Call OI（上方压力）</text>')
    parts.append('<rect x="44" y="34" width="9" height="9" rx="2" fill="#00B8B8" opacity="0.85"/><text x="57" y="42" font-size="9" fill="rgba(0,0,0,0.55)">Put OI（下方支撑）</text>')
    return (f'<svg viewBox="0 0 {W} 228" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{CODE} 期权持仓分布与墙">' + "".join(parts) + "</svg>")


# 断言层：渲染前最后一道守门
for c in D["puts"] + D["calls"]:
    assert abs(c["prob_otm"] + abs(c["delta"]) - 1) < 0.001
    assert 28 <= c["dte"] <= 46
assert D["oi_dist"][f"{CW:g}"][0] == max(v[0] for v in D["oi_dist"].values())
assert D["oi_dist"][f"{PW:g}"][1] == max(v[1] for v in D["oi_dist"].values())

CSS = """
  :root { --brand:#00B8B8; --brand-active:#008080; --brand-secondary:#E5F8F8;
    --mark-teal:#00DBB6; --mark-orange:#FC5200; --mark-yellow:#FFE000;
    --loss:#FF3A75; --bg:#FFFFFF; --bg-page:#F8F9FA; --border:#E6E7E8; --divide:#DDDDDF;
    --text-primary:rgba(0,0,0,0.85); --text-secondary:rgba(0,0,0,0.55); --text-tertiary:#82888D;
    --ff-display:"Cera Pro","Source Han Sans CN","PingFang SC",system-ui,sans-serif;
    --ff-body:"Cera Pro","Source Han Sans CN","PingFang SC",ui-sans-serif,system-ui,sans-serif;
    --ff-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
  @page { size: A4 portrait; margin: 0; }
  * { box-sizing: border-box; } html, body { margin:0; padding:0; }
  body { font-family:var(--ff-body); color:var(--text-primary); background:#DCDCE0;
         font-size:9.5pt; line-height:1.5; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  .page { width:210mm; height:297mm; background:var(--bg); position:relative; overflow:hidden;
          display:flex; flex-direction:column; page-break-after:always; }
  .page:last-child { page-break-after:auto; }
  @media screen { body{padding:24px 0;} .page{margin:0 auto 24px; box-shadow:0 4px 16px rgba(0,0,0,.18);} }
  @media print { body{background:#fff;padding:0;} .page{box-shadow:none;margin:0;} }
  .topstripe { height:5mm; background:var(--brand); flex:none; }
  .content { padding:6mm 16mm 0; flex:1; display:flex; flex-direction:column; }
  .masthead { display:flex; align-items:center; justify-content:space-between; }
  .masthead .mark { display:flex; align-items:center; gap:10px; }
  .masthead svg.logo { width:24px; height:23px; }
  .masthead .word { font-family:var(--ff-display); font-weight:700; font-size:12pt; letter-spacing:.04em; }
  .masthead .word .sub { display:block; font-size:6.5pt; font-weight:500; letter-spacing:.2em;
                         color:var(--text-secondary); text-transform:uppercase; margin-top:1pt; }
  .masthead .meta { font-family:var(--ff-mono); font-size:7pt; color:var(--text-tertiary);
                    text-transform:uppercase; letter-spacing:.08em; text-align:right; line-height:1.7; }
  .titleblock { margin-top:3mm; }
  .eyebrow { font-family:var(--ff-mono); font-size:8pt; letter-spacing:.18em; text-transform:uppercase; color:var(--brand-active); }
  h1.title { font-family:var(--ff-display); font-size:19pt; font-weight:700; letter-spacing:-.01em; margin:1.5mm 0 1mm; line-height:1.2; }
  .subtitle { font-size:9.5pt; color:var(--text-secondary); margin:0; }
  .symhead { margin-top:4mm; display:flex; align-items:baseline; justify-content:space-between;
             border-bottom:1pt solid var(--text-primary); padding-bottom:1.6mm; }
  .symhead .l { display:flex; align-items:baseline; gap:4mm; }
  .symhead .tk { font-family:var(--ff-display); font-size:17pt; font-weight:700; }
  .symhead .cn { font-size:10.5pt; color:var(--text-secondary); }
  .symhead .tone { font-family:var(--ff-mono); font-size:7.5pt; color:var(--brand-active);
                   letter-spacing:.1em; text-transform:uppercase; }
  .statrow { display:grid; grid-template-columns:repeat(4,1fr); gap:4mm; margin-top:0;
             border-bottom:0.5pt solid var(--border); padding:1.8mm 0; }
  .stat .k { font-family:var(--ff-mono); font-size:7pt; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:.08em; }
  .stat .v { font-family:var(--ff-display); font-size:13pt; font-weight:700; font-variant-numeric:tabular-nums; }
  h2.sec { font-family:var(--ff-display); font-size:11.5pt; font-weight:700; margin:3mm 0 1.2mm;
           padding-bottom:1.2mm; border-bottom:1pt solid var(--text-primary); display:flex; align-items:baseline; gap:3mm; }
  h2.sec .num { font-family:var(--ff-mono); font-size:8.5pt; color:var(--brand); font-weight:700; }
  h2.sec .ai { font-family:var(--ff-mono); font-size:6.5pt; color:#fff; background:var(--brand-active);
               padding:.3mm 2mm; border-radius:2pt; letter-spacing:.1em; margin-left:auto; }
  p.body { margin:0; font-size:9.5pt; color:var(--text-primary); }
  .aibox { background:var(--brand-secondary); border-left:2pt solid var(--brand); padding:2mm 3.5mm; }
  .aibox p { margin:0; font-size:9.5pt; }
  table.kpi { width:100%; border-collapse:collapse; font-size:9pt; margin-top:1mm; }
  table.kpi td { border-bottom:0.5pt solid var(--border); padding:1mm 2mm; }
  table.kpi td.k { font-family:var(--ff-mono); font-size:8pt; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:.04em; width:40mm; }
  table.kpi td.k i { display:block; font-style:normal; font-family:var(--ff-body); font-size:7.5pt;
                     color:var(--text-secondary); text-transform:none; letter-spacing:0; margin-top:.3mm; }
  table.kpi td.v { font-family:var(--ff-mono); font-weight:700; font-variant-numeric:tabular-nums; width:30mm; }
  table.kpi td.m { color:var(--text-secondary); }
  figure.oimap { margin:1.5mm 0 0; border:0.5pt solid var(--border); padding:2mm 2.5mm 0.5mm; }
  figure.oimap svg { display:block; }
  figcaption { font-family:var(--ff-mono); font-size:7pt; color:var(--text-tertiary);
               text-transform:uppercase; letter-spacing:.08em; margin-top:1mm; }
  .fignote { font-size:8.5pt; color:var(--text-secondary); margin:1mm 0 0; }
  .sidehead { font-family:var(--ff-mono); font-size:8pt; font-weight:700; letter-spacing:.12em;
              text-transform:uppercase; padding:1.4mm 2.5mm; margin-top:2.5mm; }
  .sidehead.put { background:var(--brand-secondary); color:var(--brand-active); }
  .sidehead.call { background:rgba(252,82,0,.08); color:#C24000; margin-top:8mm; }
  .stratline { margin:1.2mm 0 0.5mm; font-size:8.5pt; color:var(--text-secondary); padding:0 2.5mm; }
  .row { display:flex; align-items:center; gap:4mm; padding:2.3mm 2.5mm; border-bottom:0.5pt solid var(--border); }
  .row:last-child { border-bottom:1pt solid var(--text-primary); }
  .row .c1 { flex:1.35; }
  .row .name { font-family:var(--ff-mono); font-size:10pt; font-weight:700; font-variant-numeric:tabular-nums; }
  .row .sub { font-size:7.5pt; color:var(--text-tertiary); margin-top:.4mm; }
  .row .tag { font-family:var(--ff-mono); font-size:7pt; border:0.5pt solid var(--divide);
              padding:.2mm 1.5mm; margin-right:1.5mm; color:var(--text-secondary); }
  .wallbadge { font-family:var(--ff-mono); font-size:6.5pt; color:#fff; background:var(--brand-active);
               padding:.3mm 1.6mm; border-radius:2pt; vertical-align:2px; }
  .wallbadge.in { background:var(--text-tertiary); }
  .row .c2 { flex:1.5; display:grid; grid-template-columns:1fr 1fr 1fr; gap:2mm; }
  .row .kv span { display:block; font-family:var(--ff-mono); font-size:6.8pt; color:var(--text-tertiary); text-transform:uppercase; }
  .row .kv b { font-family:var(--ff-mono); font-size:8.8pt; font-weight:600; font-variant-numeric:tabular-nums; }
  .row .c3 { flex:0 0 28mm; text-align:right; font-family:var(--ff-display); font-size:14pt; font-weight:700; font-variant-numeric:tabular-nums; }
  .row .c3 small { display:block; font-size:6.5pt; font-weight:500; color:var(--text-tertiary); font-family:var(--ff-mono); text-transform:uppercase; }
  .c3.put { color:var(--brand-active); } .c3.call { color:#C24000; }
  .rules-line { margin-top:2.5mm; font-size:8pt; color:var(--text-secondary); background:var(--bg-page);
                border-left:2pt solid var(--brand); padding:1.8mm 3mm; }
  .callout { margin-top:2mm; padding:2mm 3.5mm; font-size:7pt; color:var(--text-secondary); }
  .callout .label { font-family:var(--ff-mono); font-size:6.8pt; font-weight:700; letter-spacing:.12em;
                    text-transform:uppercase; display:block; margin-bottom:.6mm; }
  .callout.spec { border-left:2pt solid var(--mark-yellow); background:rgba(255,224,0,.10); }
  .callout.spec .label { color:#8A7500; }
  .callout.warn { border-left:2pt solid var(--mark-orange); background:rgba(252,82,0,.06); }
  .callout.warn .label { color:#C24000; }
  .edit-toolbar { position:fixed; top:10px; right:14px; z-index:50; display:flex; align-items:center; gap:3mm;
    background:var(--bg); border:0.5pt solid var(--divide); border-radius:6px; padding:2mm 3mm;
    box-shadow:0 2px 10px rgba(0,0,0,.15); max-width:88mm; }
  .edit-toolbar button { font-family:var(--ff-body); font-size:8.5pt; padding:1.4mm 3.5mm; white-space:nowrap;
    border:0.5pt solid var(--divide); border-radius:4pt; background:var(--bg); cursor:pointer; color:var(--text-primary); }
  .edit-toolbar button:hover { border-color:var(--brand); color:var(--brand-active); }
  .edit-toolbar .hint { font-size:7.5pt; color:var(--text-tertiary); }
  [data-ed] { transition:outline-color .15s; outline:1.5px dashed transparent; outline-offset:2px; border-radius:2px; }
  [data-ed]:hover { outline-color:var(--divide); }
  [data-ed]:focus { outline-color:var(--brand); background:rgba(0,184,184,.04); }
  @media print { .edit-toolbar { display:none; } [data-ed] { outline:none !important; } }
  .pagefoot { margin-top:auto; padding:2.2mm 16mm; display:flex; justify-content:space-between;
              font-family:var(--ff-mono); font-size:7pt; color:var(--text-tertiary);
              letter-spacing:.06em; text-transform:uppercase; border-top:0.5pt solid var(--border); }
  .bottomstripe { height:2mm; display:flex; flex:none; }
  .bottomstripe i { display:block; height:100%; }
  .bottomstripe .a { flex:0 0 28%; background:var(--mark-teal); }
  .bottomstripe .b { flex:0 0 8%; background:var(--mark-yellow); }
  .bottomstripe .c { flex:0 0 12%; background:var(--mark-orange); }
  .bottomstripe .d { flex:1; background:var(--text-primary); }
"""

LOGO = """<svg class="logo" viewBox="0 0 23 22" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<rect x=".49" y="-.02" width="1.1" height="22.02" fill="#000"/><rect x="7.10" y="19.25" width="2.75" height="2.75" fill="#FFE000"/>
<rect x="10.95" y="19.25" width="1.1" height="2.75" fill="#000"/><rect x="17.55" y="13.74" width="2.75" height="8.26" fill="#000"/>
<rect x="21.41" y="8.24" width="1.1" height="13.76" fill="#FC5200"/><rect x="13.15" y="16.50" width="3.3" height="5.5" fill="#FC5200"/>
<rect x="2.69" y="-.02" width="3.3" height="22.02" fill="#00DBB6"/></svg>"""


def masthead(pg, total):
    return f"""<div class="masthead"><div class="mark">{LOGO}
    <div class="word">LONGBRIDGE<span class="sub">Options Seller Report</span></div></div>
    <div class="meta">期权卖方报告 · {CODE}<br/>数据截至 {D['asof']} · 第 {pg} / {total} 页</div></div>"""


def footer():
    return """<div class="pagefoot"><span>Longbridge · 期权卖方报告 · 自助生成</span>
    <span>数据源：Longbridge 行情 · 本机实时快照</span></div>
    <div class="bottomstripe"><i class="a"></i><i class="b"></i><i class="c"></i><i class="d"></i></div>"""


iv_txt = f"{_iv:.0f}%" if _iv else "—"
mp_txt = f"${MP['strike']:g}" if MP.get("strike") else "—"
chg_txt = f" ({D['chg_pct']:+.1f}%)" if D.get("chg_pct") is not None else ""
page1 = f"""
<article class="page"><div class="topstripe"></div><div class="content">
  {masthead(1, 2)}
  <div class="titleblock">
    <div class="eyebrow">Options Seller · 单标的 · 双向 · 三档</div>
    <h1 class="title">{SEGMENTS['series_title']}</h1>
    <p class="subtitle">{SEGMENTS['series_sub']}</p>
  </div>
  <div class="edit-toolbar">
    <button id="ed-export">导出编辑版 HTML</button>
    <button id="ed-reset">还原原文</button>
    <span class="hint">结论文字点击可改，自动保存在本浏览器</span>
  </div>
  <div class="symhead">
    <div class="l"><span class="tk">{CODE}</span><span class="cn">{SEGMENTS['sym_cn']}</span></div>
    <span class="tone" data-ed="sym_tone">{SEGMENTS['sym_tone']}</span>
  </div>
  <div class="statrow">
    <div class="stat"><div class="k">现价</div><div class="v">${SPOT:g}<small style="font-size:8pt;color:var(--text-secondary)">{chg_txt}</small></div></div>
    <div class="stat"><div class="k">平值 IV / HV</div><div class="v">{iv_txt} / {_hv:.0f}%</div></div>
    <div class="stat"><div class="k">窗口双墙</div><div class="v">${CW:g} / ${PW:g}</div></div>
    <div class="stat"><div class="k">下次财报</div><div class="v" data-ed="next_earnings">{NEXT_EARNINGS}</div></div>
  </div>

  <h2 class="sec"><span class="num">01</span>今日热点<span class="ai">AI 视角</span></h2>
  <p class="body" data-ed="m1">{SEGMENTS['m1']}</p>

  <h2 class="sec"><span class="num">02</span>期权盘面定调<span class="ai">AI 视角</span></h2>
  <div class="aibox"><p data-ed="m2">{SEGMENTS['m2']}</p></div>

  <h2 class="sec"><span class="num">03</span>指标支撑</h2>
  <table class="kpi">
    <tr><td class="k">PCR · OI（窗口）<i>看跌 ÷ 看涨持仓</i></td><td class="v">{KPI['pcr_oi_window']:.3f}</td><td class="m" data-ed="kpi_pcr">{SEGMENTS['kpi_meaning']['pcr']}</td></tr>
    <tr><td class="k">30D ATM IV<i>期权价里的波动预期</i></td><td class="v">{iv_txt if not _iv else f"{_iv:.1f}%"}</td><td class="m" data-ed="kpi_iv">{SEGMENTS['kpi_meaning']['iv']}</td></tr>
    <tr><td class="k">HV (30D)<i>实际走出来的波动</i></td><td class="v">{_hv:.1f}%</td><td class="m" data-ed="kpi_hv">{SEGMENTS['kpi_meaning']['hv']}</td></tr>
    <tr><td class="k">IV − HV<i>预期 − 现实</i></td><td class="v">{PLACEHOLDERS['spread']}pp</td><td class="m" data-ed="kpi_spread">{SEGMENTS['kpi_meaning']['spread']}</td></tr>
    <tr><td class="k">MAX PAIN<i>让最多期权作废的价</i></td><td class="v">{mp_txt}</td><td class="m" data-ed="kpi_mp">{SEGMENTS['kpi_meaning']['max_pain']}</td></tr>
    <tr><td class="k">窗口双墙<i>持仓最厚的两档</i></td><td class="v">${CW:g} / ${PW:g}</td><td class="m" data-ed="kpi_walls">{SEGMENTS['kpi_meaning']['walls']}</td></tr>
  </table>

  <h2 class="sec"><span class="num">04</span>期权墙 · 持仓分布</h2>
  <figure class="oimap">{oi_chart()}
    <figcaption>OI 按 {EXP_LABELS} 到期日合计（与筛选窗口一致）· 现价 ${SPOT:g}</figcaption>
  </figure>
  <p class="fignote" data-ed="fignote"><b>读图：</b>{SEGMENTS['m4_note']}</p>
</div>{footer()}</article>"""

page2 = f"""
<article class="page"><div class="topstripe"></div><div class="content">
  {masthead(2, 2)}
  <h2 class="sec" style="margin-top:4mm"><span class="num">05</span>卖方合约筛选示例 · 双向三档</h2>
  <div class="sidehead put">现金担保看跌 · SELL PUT —— 手里有现金（占用现金 = 行权价 × 100）</div>
  <p class="stratline" data-ed="strat_put">{SEGMENTS['strat_put']}</p>
  {leg_rows(D['puts'], 'put')}
  <div class="sidehead call">股票担保看涨 · SELL CALL —— 手里有 100 股（门槛 ≈ ${SPOT * 100:,.0f}）</div>
  <p class="stratline" data-ed="strat_call">{SEGMENTS['strat_call']}</p>
  {leg_rows(D['calls'], 'call')}

  <div class="rules-line"><b>常见管理惯例（45/21/50）：</b>业内常见做法是浮盈达最大利润一半即平仓，剩 21 天未达利润线平仓或滚动到下月同 delta；被行权本就是该策略的组成部分——接货价与交货价都是事先选定的价位。</div>

  <div class="callout spec" style="margin-top:2.5mm"><span class="label">口径说明</span>
    「今日热点」「盘面定调」为 AI 基于当日数据与公开新闻生成的观点性内容，仅代表数据视角；合约由既定规则筛出（财报落在窗口内拒出报告 → OI≥10 & 权利金≥$0.05 → delta 定档 → 档内评分取优），「墙外」= 行权价位于对应主墙之上（Call）或之下（Put）。年化回报率按现金担保全额计算（看跌按行权价全额、看涨按正股市值），未使用杠杆；权利金为最新成交价；价外概率 ≈ 1−|Δ|；delta 由隐含波动率经 Black-Scholes 计算。OI 分布、双墙与 PCR 均按筛选窗口（{EXP_LABELS} 到期）合计；Max Pain 按窗口内最近到期日（{int(MP['expiry'][5:7])}/{int(MP['expiry'][8:10])}）计算。数据基于 {D['asof']} 本机实时快照。
  </div>
  <div class="callout warn"><span class="label">风险披露</span>
    本内容仅作期权知识介绍与教学展示，并非及不应被视为任何证券、金融产品或工具的邀约、要约、招揽、邀请、或任何投资决策的建议，亦不应被视为专业意见；文中合约由既定规则从市场数据中筛出，仅为教学示例，不构成对任何标的的推荐。期权为复杂产品，交易规则较为复杂，非保本，买卖期权合约的亏蚀风险可能极大：卖出看跌期权的最大亏损为行权价全额（扣除权利金），卖出看涨期权将放弃行权价以上的全部涨幅。请确认您已充分掌握期权交易的规则，并了解期权价格与股票价格走势之间的联系后，评估是否可以承担投资期权带来的风险，然后再开始进入期权交易。本页面如有类似前瞻性陈述之内容，此等内容或陈述不得视为对任何将来表现之保证，且应注意实际情况或发展可能与该等陈述有重大落差。以上图表及案例仅为模拟计算，用作教学展示，未计入佣金、平台费、交易所费用等交易成本，实际损益将有所不同。投资涉及风险，投资产品价格可升可跌，入市需谨慎。
  </div>
</div>{footer()}</article>"""

EDIT_JS = """
<script>
(function () {
  var KEY = 'options-seller:' + %s + ':';
  var els = document.querySelectorAll('[data-ed]');
  var orig = {};
  els.forEach(function (el) {
    var k = el.dataset.ed;
    orig[k] = el.innerHTML;
    el.contentEditable = 'true';
    el.spellcheck = false;
    try { var saved = localStorage.getItem(KEY + k); if (saved !== null) el.innerHTML = saved; } catch (e) {}
    el.addEventListener('input', function () { try { localStorage.setItem(KEY + k, el.innerHTML); } catch (e) {} });
  });
  document.getElementById('ed-reset').addEventListener('click', function () {
    els.forEach(function (el) { var k = el.dataset.ed; el.innerHTML = orig[k]; try { localStorage.removeItem(KEY + k); } catch (e) {} });
  });
  document.getElementById('ed-export').addEventListener('click', function () {
    var clone = document.documentElement.cloneNode(true);
    clone.querySelectorAll('.edit-toolbar, script').forEach(function (n) { n.remove(); });
    clone.querySelectorAll('[data-ed]').forEach(function (n) { n.removeAttribute('contenteditable'); n.removeAttribute('spellcheck'); });
    var blob = new Blob(['<!doctype html>' + clone.outerHTML], { type: 'text/html' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = %s;
    a.click(); URL.revokeObjectURL(a.href);
  });
})();
</script>
""" % (json.dumps(f"{CODE}-{D['asof']}"), json.dumps(f"期权卖方报告-{CODE}-{D['asof']}-编辑版.html"))

html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>期权卖方报告 · {CODE} · {D['asof']}</title>
<style>{CSS}</style></head><body>
{page1}
{page2}
{EDIT_JS}
</body></html>"""
OUT = f"期权卖方报告-{CODE}-{D['asof']}.html"
with open(OUT, "w") as f:
    f.write(html)
print(f"written {OUT} ({len(html):,} bytes)")
