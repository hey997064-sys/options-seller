#!/bin/bash
# 发版前离线回归（无需网络/登录）：./tests/run_tests.sh [python解释器，默认 /usr/bin/python3]
# 覆盖：故障矩阵退出码契约 / 零AI全流程 / 责任分区标签 / mutation 防篡改。
set -u
PY="${1:-/usr/bin/python3}"
PY="$(command -v "$PY" || echo "$PY")"   # 先解析为绝对路径，防止下面的 PATH 覆盖换掉解释器
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/options-seller/skills/options-seller/scripts"
TMP="$(mktemp -d)"
mkdir -p "$TMP/bin"
cp "$ROOT/tests/mock_longbridge" "$TMP/bin/longbridge" && chmod +x "$TMP/bin/longbridge"
export PATH="$TMP/bin:/usr/bin:/bin"
cd "$TMP"
PASS=0; FAIL=0
chk() { # chk <名称> <期望exit> <实际exit>
  if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "  ✓ $1 (exit $3)";
  else FAIL=$((FAIL+1)); echo "  ✗ $1 期望 exit $2 实际 $3"; fi
}

echo "== 故障矩阵"
PATH="/usr/bin:/bin" "$PY" "$S/doctor.py" >/dev/null 2>&1; chk "无CLI→doctor拒绝" 1 $?
LB_MODE=nologin "$PY" "$S/doctor.py" >/dev/null 2>&1;     chk "未登录→doctor拒绝" 1 $?
LB_MODE=nochain "$PY" "$S/seller_fetch.py" MOCK >/dev/null 2>&1; chk "无期权链→exit3" 3 $?
LB_MODE=nooi   "$PY" "$S/seller_fetch.py" MOCK >/dev/null 2>&1;  chk "无行情权限→exit6" 6 $?
"$PY" "$S/seller_fetch.py" >/dev/null 2>&1;               chk "缺参数→exit2" 2 $?
"$PY" "$S/seller_fetch.py" 'BAD-1' >/dev/null 2>&1;       chk "非法代码→exit2" 2 $?

echo "== 脏数据族（应收敛为 exit4 人话，无裸 traceback）"
for m in quotedict missingfield klinenoclose nullcal; do
  ERR=$(LB_MODE=$m "$PY" "$S/seller_fetch.py" MOCK 2>&1 >/dev/null); rc=$?
  chk "LB_MODE=$m→exit4" 4 $rc
  echo "$ERR" | grep -q "Traceback"; [ $? -ne 0 ]; chk "  $m 无裸traceback" 0 $?
done

echo "== zerocall（call OI 全 0：PCR 置空 + 缺档提示，不崩）"
LB_MODE=zerocall "$PY" "$S/seller_fetch.py" MOCK >/dev/null 2>&1; chk "zerocall 取数" 0 $?
LB_MODE=zerocall "$PY" "$S/make_segments.py" --force >/dev/null 2>&1 && "$PY" "$S/build_report.py" >/dev/null 2>&1
chk "zerocall 渲染" 0 $?
HZ=$(ls -t 期权卖方报告-MOCK-*.html | head -1)
grep -q "档本期无符合筛选条件的合约" "$HZ"; chk "缺档提示在场" 0 $?
rm -f seller_data.json segments.json

echo "== 零 AI 全流程（LB_MODE=ok 离线）"
"$PY" "$S/run.py" MOCK --skip-doctor --no-open >/dev/null 2>&1; chk "run.py 一键全流程" 0 $?
H=$(ls 期权卖方报告-MOCK-*.html 2>/dev/null | head -1)
[ -n "$H" ]; chk "产出 HTML" 0 $?
grep -q "自动摘要" "$H";      chk "零AI挂「自动摘要」标" 0 $?
! grep -q "AI 视角" "$H";     chk "零AI不得出现「AI 视角」" 0 $?
grep -q "风险披露" "$H";      chk "风险披露在场" 0 $?
grep -q "口径说明" "$H";      chk "口径说明在场" 0 $?
! grep -qE '\{(spot|cw|pw|iv|hv|mp_strike)\}' "$H"; chk "无占位符残留" 0 $?

echo "== 责任分区：AI 模式标签"
"$PY" - <<PYEOF
import json
d = json.load(open("segments.json")); d["_source"] = "ai"
json.dump(d, open("segments.json", "w"), ensure_ascii=False)
PYEOF
"$PY" "$S/build_report.py" >/dev/null 2>&1; chk "AI 模式渲染" 0 $?
grep -q "AI 视角" "$H";  chk "AI 模式挂「AI 视角」标" 0 $?

echo "== segments 容错（B 级外部 AI 产出）"
"$PY" - <<PYEOF
import json
d = json.load(open("segments.json")); d.pop("m2"); d["kpi_meaning"].pop("walls")
json.dump(d, open("segments_bad.json", "w"), ensure_ascii=False)
d2 = json.load(open("segments.json")); d2["m2"] = "含裸花括号 { 的 AI 文字，且有未知占位符 {gamma}"
json.dump(d2, open("segments_brace.json", "w"), ensure_ascii=False)
PYEOF
ERR=$("$PY" "$S/build_report.py" --segments segments_bad.json 2>&1 >/dev/null); rc=$?
chk "缺必填字段→exit1" 1 $rc
echo "$ERR" | grep -q "m2"; chk "  报错点名缺失字段" 0 $?
"$PY" "$S/build_report.py" --segments segments_brace.json >/dev/null 2>&1
chk "裸花括号/未知占位符→容错渲染" 0 $?

echo "== mutation：数字防篡改"
"$PY" - <<PYEOF
import json
d = json.load(open("seller_data.json"))
d["puts"][0]["ann"] = round(d["puts"][0]["ann"] * 1.5, 4)
json.dump(d, open("seller_data_bad.json", "w"))
PYEOF
"$PY" "$S/build_report.py" --data seller_data_bad.json >/dev/null 2>&1
[ $? -ne 0 ]; chk "篡改年化→拒渲染" 0 $?

echo
echo "结果: $PASS 通过, $FAIL 失败  (解释器: $($PY --version 2>&1))"
rm -rf "$TMP"
[ "$FAIL" = 0 ]
