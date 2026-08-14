# Options Seller · 期权卖方报告

输入一个美股标的，在你自己的机器上一键生成**期权卖方合约筛选报告**（双页 A4）：

- 双向 × 三档：sell put（现金担保看跌）/ covered call（股票担保看涨）× 稳健 Δ0.2 / 均衡 Δ0.3 / 进取 Δ0.4
- 期权墙 OI 分布图、IV/HV 租金定价、窗口 PCR、Max Pain
- 财报落在持仓窗口内自动拒跑（期权卖方最忌财报夜）
- 全部计算在本机完成，数据来自你自己的长桥行情权限；报告文字可点击直改后导出分享

## 安装（三步）

1. **安装并登录 longbridge CLI**（需要长桥账户，且已开通**美股期权行情**）
2. 在 Claude Code 中添加市场并安装插件：
   ```
   /plugin marketplace add hey997064-sys/options-seller
   /plugin install options-seller@options-seller-market
   ```
> 不走 marketplace 也可手动 `git clone` 本仓库使用：插件根目录 = `<仓库>/options-seller/`

3. 自检环境（首次）：对 Claude 说 **"检查一下期权卖方报告的环境"**，或直接开始使用，skill 会先跑 doctor 自检

## 使用（按你手里有什么 AI，三选一）

**A · 有 Claude Code / Cowork**（全自动，体验最好）

> 出一份 NVDA 的卖方报告 / 帮我看看 TSLA 能卖什么期权 / /options-seller INTC

约 1–2 分钟后浏览器自动打开报告，热点与盘面段由 AI 撰写（页面挂「AI 视角」标）。

**B · 用别的 AI 助手**（ChatGPT / Kimi / 豆包等都行）

```bash
python3 <插件目录>/skills/options-seller/scripts/run.py NVDA
```

先得到一份"自动摘要"版报告；想升级成 AI 撰写版，把 `skills/options-seller/PROMPT.md` 全文 + 生成的 `seller_data.json` 发给你的 AI 助手，把它返回的 JSON 存为 `segments.json`，再跑一次 `build_report.py` 即可。

**C · 完全不用 AI**（一条命令）

同上 `run.py NVDA` 直接用：合约筛选、期权墙、KPI 全部照常（这些本来就是机械规则），两段文字为固定规则生成的数据陈述，页面挂「自动摘要」标以示区分。

报告中的合约行、图表与指标在三种用法下完全一致——AI 只负责两段解读文字，从不碰数字。

## 出问题了？

| 现象 | 原因与处理 |
|---|---|
| 提示无期权行情权限 | 在长桥 App 行情商店开通美股期权行情（按账户开通，本工具无法代开） |
| 提示财报在窗口内拒跑 | 设计行为：财报夜波动会击穿卖方策略。想换标的或等财报后再跑 |
| 提示窗口内无到期日 | 该标的只有远月期权，不符合 30–45 天开仓窗，换标的 |
| 个别报价块失败 warn | 网络抖动，OI 分布可能不完整，重跑一次即可 |

先跑自检可以定位绝大多数问题：`python3 <插件目录>/skills/options-seller/scripts/doctor.py`

## 依赖与边界

- 仅美股标的；纯 Python 标准库（无 pip 依赖）；macOS / Linux
- 口径：年化回报按现金担保全额计算；delta 由 IV 经 Black-Scholes 本地计算（r=2.5%，与 App 展示口径对账校准）；价外概率 ≈ 1−|Δ|
- 本工具输出为教学示例与数据展示，不构成投资建议；完整风险披露见报告页尾

## 版本

见 [CHANGELOG](CHANGELOG.md)。当前 0.1.0。
