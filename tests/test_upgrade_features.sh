#!/bin/bash
# OMKA 升级计划 — 功能测试脚本
# 使用方法: bash tests/test_upgrade_features.sh
# Windows PowerShell: 逐段执行 curl 命令

set -e
BASE_URL="${OMKA_BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0

log_pass() { echo "  ✅ PASS: $1"; PASS=$((PASS+1)); }
log_fail() { echo "  ❌ FAIL: $1"; FAIL=$((FAIL+1)); }

echo "=========================================="
echo " OMKA 升级功能测试"
echo " Target: $BASE_URL"
echo "=========================================="

# ========================================
# 1. 健康检查
# ========================================
echo ""
echo "[1/7] 健康检查"
if curl -sf "$BASE_URL/health" > /dev/null 2>&1; then
    log_pass "服务运行中"
else
    log_fail "服务未启动"; exit 1
fi

# ========================================
# 2. 定时任务 API (M1: SchedulerService)
# ========================================
echo ""
echo "[2/7] 定时任务 API (GET /jobs/schedule)"
SCHEDULE=$(curl -sf "$BASE_URL/jobs/schedule")
CRON=$(echo "$SCHEDULE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cron',''))" 2>/dev/null || echo "")
NEXT_RUN=$(echo "$SCHEDULE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('next_run_time',''))" 2>/dev/null || echo "")

if [ -n "$CRON" ] && [ -n "$NEXT_RUN" ]; then
    log_pass "GET /jobs/schedule: cron=$CRON next=$NEXT_RUN"
else
    log_fail "GET /jobs/schedule 返回数据不完整: $SCHEDULE"
fi

echo ""
echo "[2/7b] 更新定时任务 (PUT /jobs/schedule)"
UPDATE_RESULT=$(curl -sf -X PUT "$BASE_URL/jobs/schedule" \
    -H "Content-Type: application/json" \
    -d '{"schedule": "每天 9:30"}' 2>/dev/null)
NEW_CRON=$(echo "$UPDATE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cron',''))" 2>/dev/null || echo "")
if [ "$NEW_CRON" = "30 9 * * *" ]; then
    log_pass "自然语言 '每天 9:30' -> cron=$NEW_CRON"
else
    log_fail "自然语言解析失败: $UPDATE_RESULT"
fi

# 恢复默认
curl -sf -X PUT "$BASE_URL/jobs/schedule" -H "Content-Type: application/json" \
    -d '{"schedule": "0 9 * * *"}' > /dev/null 2>&1

# ========================================
# 3. 自然语言时间解析 (M1)
# ========================================
echo ""
echo "[3/7] 自然语言时间解析测试"
declare -A TEST_CASES=(
    ["每天 9:30"]="30 9 * * *"
    ["每天 14 点"]="0 14 * * *"
    ["每周一 18:00"]="0 18 * * mon"
    ["0 9 * * *"]="0 9 * * *"  # 直接 cron 保持不变
)

for input in "${!TEST_CASES[@]}"; do
    expected="${TEST_CASES[$input]}"
    result=$(curl -sf -X PUT "$BASE_URL/jobs/schedule" \
        -H "Content-Type: application/json" \
        -d "{\"schedule\": \"$input\"}" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('cron',''))" 2>/dev/null)
    if [ "$result" = "$expected" ]; then
        log_pass "'$input' -> $result"
    else
        log_fail "'$input': expected $expected, got $result"
    fi
done

# 恢复默认
curl -sf -X PUT "$BASE_URL/jobs/schedule" -H "Content-Type: application/json" \
    -d '{"schedule": "0 9 * * *"}' > /dev/null 2>&1

# ========================================
# 4. 无效输入拒绝 (M1)
# ========================================
echo ""
echo "[4/7] 无效输入拒绝测试"
BAD_RESULT=$(curl -sf -X PUT "$BASE_URL/jobs/schedule" \
    -H "Content-Type: application/json" \
    -d '{"schedule": "下周三下午两三点左右"}' 2>/dev/null || true)
if [ -n "$BAD_RESULT" ]; then
    IS_400=$(echo "$BAD_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('detail' in d)" 2>/dev/null)
    if [ "$IS_400" = "True" ]; then
        log_pass "无效输入正确返回 400 错误"
    else
        log_fail "无效输入未拒绝: $BAD_RESULT"
    fi
fi

# ========================================
# 5. Settings API 接入 reschedule (M2)
# ========================================
echo ""
echo "[5/7] Settings API 接入运行时 reschedule (PUT /settings)"
# 通过 Settings API 修改 cron
curl -sf -X POST "$BASE_URL/settings/scheduler_daily_cron" \
    -H "Content-Type: application/json" \
    -d '{"value": "0 20 * * *"}' > /dev/null 2>&1
sleep 1
VERIFY_SCHEDULE=$(curl -sf "$BASE_URL/jobs/schedule" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cron',''))" 2>/dev/null)
if [ "$VERIFY_SCHEDULE" = "0 20 * * *" ]; then
    log_pass "Settings API 更新 cron 后 scheduler 同步生效"
else
    log_fail "Settings API 更新后 scheduler 未同步: $VERIFY_SCHEDULE"
fi

# 恢复
curl -sf -X POST "$BASE_URL/settings/scheduler_daily_cron" \
    -H "Content-Type: application/json" \
    -d '{"value": "0 9 * * *"}' > /dev/null 2>&1

# ========================================
# 6. 搜索质量配置 (M4)
# ========================================
echo ""
echo "[6/7] 搜索质量配置"
SEARCH_SETTINGS=$(curl -sf "$BASE_URL/settings" | python3 -c "
import sys,json
d=json.load(sys.stdin)['settings']
keys=['search_qualifiers','search_min_stars','search_max_candidates_per_query','search_expand_queries','candidate_score_threshold']
for k in keys:
    print(f'{k}={d.get(k,\"MISSING\")}')
" 2>/dev/null)

for check in "search_qualifiers" "search_min_stars" "search_max_candidates_per_query" "candidate_score_threshold"; do
    if echo "$SEARCH_SETTINGS" | grep -q "$check"; then
        log_pass "配置存在: $check"
    else
        log_fail "配置缺失: $check"
    fi
done

# ========================================
# 7. 数据源运行 (验证 M4 质量过滤不破坏现有功能)
# ========================================
echo ""
echo "[7/7] 数据源运行 (功能完整性)"
ACTIVE_SOURCES=$(curl -sf "$BASE_URL/sources" | python3 -c "
import sys,json
sources=json.load(sys.stdin)
enabled=[s['id'] for s in sources if s.get('enabled')]
print(len(enabled))
" 2>/dev/null)
if [ "$ACTIVE_SOURCES" -gt 0 ] 2>/dev/null; then
    log_pass "活跃数据源: $ACTIVE_SOURCES 个"
else
    log_fail "无活跃数据源"
fi

# ========================================
# 总结
# ========================================
echo ""
echo "=========================================="
echo " 测试完成"
echo " PASS: $PASS | FAIL: $FAIL"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
