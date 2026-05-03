# OMKA 升级计划 — 调试与测试指南

## 启动服务

```bash
cd E:\GitHub\Repositories\oh-my-knowledge-assistant

# 1. 后端
python -m omka.app.main

# 2. 前端 (另一个终端)
cd frontend
npm run dev
```

## 自动化测试

```bash
# Linux/Mac
bash tests/test_upgrade_features.sh

# Windows PowerShell (手动逐段执行)
curl http://localhost:8000/health
curl http://localhost:8000/jobs/schedule
```

## 手动验证各里程碑

### M1: 定时任务 API

```bash
# 查看当前定时任务
curl http://localhost:8000/jobs/schedule
# → {"cron":"0 9 * * *","timezone":"Asia/Shanghai","next_run_time":"...","running":true}

# 设置为每天 9:30
curl -X PUT http://localhost:8000/jobs/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "每天 9:30"}'
# → {"cron":"30 9 * * *","next_run_time":"..."}

# 设置为每周一 18:00
curl -X PUT http://localhost:8000/jobs/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "每周一 18:00"}'

# 无效输入
curl -X PUT http://localhost:8000/jobs/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "下周三下午两点"}'
# → 400 Bad Request
```

### M2: Settings 同步

```bash
# 通过 Settings API 改 cron
curl -X POST http://localhost:8000/settings/scheduler_daily_cron \
  -H "Content-Type: application/json" \
  -d '{"value": "30 14 * * *"}'

# 确认 scheduler 已同步
curl http://localhost:8000/jobs/schedule | python -m json.tool
# cron 应为 "30 14 * * *"，next_run_time 已更新
```

### M3: 飞书命令（需要飞书群配置）

```
/omka schedule                           # 查看定时任务
/omka schedule set 每天 9:30             # 设置
/omka schedule set 每周一 18:00          # 设置
每天 9 点跑          (自然语言→NLU)      # 自动转 schedule.set
```

### M4: 搜索质量

```bash
# 启用多策略召回（可选，默认关闭）
# 编辑 .env: SEARCH_EXPAND_QUERIES=true
# 或在 Settings UI 中修改 search_expand_queries

# 手动运行搜索源
curl -X POST http://localhost:8000/sources/src_search_Hermes/run

# 查看候选的质量分
python -c "
import sqlite3, json
conn = sqlite3.connect('data/db/app.sqlite')
rows = conn.execute('''SELECT c.title, c.score,
    json_extract(c.score_detail, '\$.source_quality_score') as sqs,
    json_extract(c.score_detail, '\$.source_quality_reasons') as sqr
    FROM candidate_items c WHERE c.status='pending' ORDER BY c.score DESC LIMIT 10''')
for r in rows:
    print(f'{r[0][:50]:50s} score={r[1]:.2f}  quality={r[2]:.2f}  reasons={r[3]}')
"
```

### M5: 前端

1. 打开 http://localhost:5173
2. Dashboard 页面 → 查看定时任务状态卡片
3. Settings → Scheduler 区域 → 输入 cron 保存 → 回到 Dashboard 确认生效

## 常见问题排查

| 问题 | 检查 |
|------|------|
| 定时任务不生效 | 检查 APScheduler 是否启动: 日志搜 "调度器已启动" |
| cron 更新后不 reschedule | 检查 `routes_settings.py` hook 是否被调用，日志搜 "调度器更新失败" |
| 搜索仍返回无关 repo | 检查 `.env` 中 SEARCH_QUALIFIERS、SEARCH_MIN_STARS 的值 |
| 多策略召回不工作 | SEARCH_EXPAND_QUERIES=true 需要重启服务 |
| 所有候选分数 0 | 运行 `curl -X POST http://localhost:8000/jobs/run-now` 触发 ranker |
