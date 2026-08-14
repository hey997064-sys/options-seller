---
name: options-seller
description: "期权卖方报告：输入美股标的（如 NVDA / TSLA / INTC），生成双向三档卖方合约筛选报告（sell put 现金担保看跌 / covered call 股票担保看涨），含期权墙 OI 分布图、IV/HV 租金定价、完整风险披露。触发：/options-seller <ticker>、卖方报告、卖出看跌、卖出看涨、sell put、covered call、收租、卖期权、做卖方、权利金。"
---

# 期权卖方报告（Options Seller Report）

输入一个美股标的，产出一份**双页 A4 品牌报告**：双向（sell put / covered call）× 三档（稳健 Δ0.2 / 均衡 Δ0.3 / 进取 Δ0.4）合约筛选示例 + 期权墙分布 + AI 盘面解读。

**分工铁律**：机械的归脚本（取数/选腿/断言/渲染），观点的归 AI（两段文字 + 含义列），拍板的归用户。

## 执行管线（四步，顺序不可变）

所有产物放独立目录（建在用户当前目录下），避免覆盖上次结果：

```bash
mkdir -p options-seller-<CODE>-$(date +%F) && cd options-seller-<CODE>-$(date +%F)
```

路径说明：`${CLAUDE_PLUGIN_ROOT}` 指向插件根目录；若是手动 git clone 使用，插件根 = `<仓库>/options-seller/`（仓库根上还有一层 marketplace 清单）。

### Step 0 · 首次使用先自检

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/options-seller/scripts/doctor.py"
```

任何 ✗ 都**停止流程**，把"修复"行原样告诉用户。全 ✓ 才继续。不确定这台机器是否检查过时，直接重跑（十几秒，无副作用）。

### Step 1 · 取数

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/options-seller/scripts/seller_fetch.py" <CODE>
```

**退出码契约（非零一律禁止渲染报告，把 stderr 人话转述给用户）：**

| 退出码 | 含义 | 你该做什么 |
|---|---|---|
| 0 | 成功，产出 seller_data.json | 继续 Step 2 |
| 2 | 参数错误 | 提示需要美股代码 |
| 3 | 无期权链 / 窗口内无到期日 | 转述原因，建议换标的 |
| 4 | 行情获取失败 | 转述 stderr，建议跑 doctor.py |
| 5 | **财报落在持仓窗口内，拒跑** | 转述财报日期与拒跑理由。仅当用户明确表示仍要继续时，才可加 `--allow-earnings` 重跑，且报告"下次财报"格会自动带 ⚠ 标注，你必须在回复里再次口头提示财报风险 |
| 6 | 疑似无美股期权行情权限 | 转述开通指引，停止 |

stderr 出现 `warn:` 前缀（个别报价块失败）不阻断，但要在最后交付时向用户提一句"OI 分布可能不完整"。

### Step 2 · 起草 segments.json（唯一的 AI 环节）

复制模板起草：模板在 `${CLAUDE_PLUGIN_ROOT}/skills/options-seller/scripts/segments.template.json`，逐字段填写后存为当前目录 `segments.json`，`_source` 保持 `"ai"`（报告据此渲染「AI 视角」标；`make_segments.py` 生成的零 AI 版为 `"auto"`，渲染「自动摘要」标——两种来源标签不可混用）。

**写作纪律（违反任意一条 = 重写）：**

1. **数字只能来自 seller_data.json**。一个例外：m1 热点段可引用 news 列表里标题包含的事实（涨跌幅、金额），但不得自行补充记忆中的数字。
2. **动态数字用占位符**，渲染时自动填：`{spot}` 现价 / `{cw}` `{pw}` 双墙 / `{cw_dist}` `{pw_dist}` 墙距% / `{mp_strike}` `{mp_dist}` MaxPain / `{iv}` `{hv}` `{spread}`。占位符之外确需写死的数字（如某档 OI 张数），必须能在 seller_data.json 里找到出处。
3. **长度**：m1 ≤3 句（只取与波动率/期权定价相关的新闻，与本次窗口无关的八卦不写）；m2 ≤180 字；kpi_meaning 每条 ≤15 字；m4_note ≤2 句。
4. **禁词**：可能 / 或许 / 大概；行话（vega、gamma、IV 分位、Greeks）；**指令与安抚性措辞**——推荐、建议、打法、盯、机会、抄底、不用担心、放心。改用：筛选示例 / 结构上看 / 业内常见做法 / 不涉及。
5. **语言范式**：把期权说给没做过期权的人听——权利金=租金、卖put=承诺接货、卖call=承诺交货、墙=持仓防线。白话优先，比喻服务于准确。
6. m1 若 news 为空或全不相关，写盘面本身（涨跌、IV 变化），不编新闻。
7. 财报若带 `--allow-earnings` 越过（earnings.next_in_window 非空），m1 必须包含一句财报日期提示。

**占位符对照（符号已含在值里，照"用法"列写，勿自作主张加正负号）：**

| 占位符 | 含义 | 符号 | 用法 |
|---|---|---|---|
| `{spot}` `{cw}` `{pw}` `{mp_strike}` | 现价 / 各侧主墙 / MaxPain 价 | 无 | `${cw}` |
| `{iv}` `{hv}` | 平值 IV / 历史波动（数值） | 无 | `{iv}%` |
| `{cw_dist}` | 上墙距现价% | 恒正、无号 | `+{cw_dist}%` |
| `{pw_dist}` | 下墙距现价% | 自带负号 | `{pw_dist}%` |
| `{mp_dist}` `{spread}` | MaxPain 距离% / IV−HV | 自带正负号 | `{mp_dist}%`、`{spread}pp` |

**细则（歧义裁定，遇到即照此执行）：**

- **术语白名单** = 报告模板已出现的词（IV、HV、PCR、Max Pain、delta/Δ、sell put、covered call）；禁的是白名单之外的行话（vega、gamma、IV 分位、Greeks、skew）
- **"不给方向判断"** 指不判断股价要涨要跌；"租金贵/打折"是 IV 与 HV 的数据对比结论，允许且必写
- **墙厚度口径** = 主墙单一行权价的窗口合计 OI（与图表标注一致），可从 oi_dist 引用原数；每侧的第二道墙在 call_walls/put_walls 数组里，需要时可写"次墙"
- `{cw}`/`{pw}` = 各侧**主墙**（OI 最大一档）
- **sym_cn**：用大众常用中文名（英伟达/苹果）；无通行中文名的标的直接写代码（AMD 就填 AMD），不生造译名
- **m1 的 ≤3 句含固定末句**（财报位置那句算在 3 句内）
- **新闻标题内数字的单位换算/进位允许**（$4.75 billion → 47.5 亿美元），不算编数
- **next_earnings**：财报在窗口外时留 null（渲染自动显示"窗口外"），不必去查具体日期
- **程度词允许**（有所/偏/相对/略），禁的是无依据的猜测语气（可能/或许/大概）
- segments.json 里 `_readme` 字段可保留，渲染时自动忽略
- 页面「AI 视角」标 = 01 今日热点、02 盘面定调两段；sym_tone 与读图注脚同为你起草，但不在该标之内

### Step 3 · 渲染并交付

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/options-seller/scripts/build_report.py"
```

（输入契约：从**当前目录**读 seller_data.json 与 segments.json，也可用 `--data/--segments` 指定。）

断言失败（AssertionError）= 数据被破坏，停止并转述，不出报告。

成功后：
- 用系统浏览器打开产出的 `期权卖方报告-<CODE>-<日期>.html`（macOS: `open <文件>`）
- 告诉用户：报告里的**结论文字可直接点击修改**（自动存在浏览器），改完点"导出编辑版 HTML"即可分享；"AI 视角"标注的两段是观点性内容，其余全部为机械规则产出。

## 你不做的事

- 不改脚本里的任何参数（delta 档、DTE 窗、流动性闸、r=2.5%）——这些是已定版口径
- 不在报告之外补充买卖建议；用户问"该不该卖"时，指出报告是筛选示例 + 风险披露，决策归用户
- 不为绕过退出码 3/5/6 找变通（换日期、编数据、跳过检查）
