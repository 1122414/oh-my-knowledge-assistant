# OMKA 升级调试与测试指南

## 一、快速启动

### 1. 启动后端服务

```bash
# 确保已安装依赖
pip install -r requirements.txt

# 启动服务
python -m omka.app.main
```

服务将在 http://localhost:8000 启动，API 文档访问 http://localhost:8000/docs

### 2. 验证数据库

```bash
# 查看数据库表结构（需要 sqlite3 命令行工具）
sqlite3 data/db/app.sqlite ".tables"

# 应包含以下新增表：
# memory_items        memory_events
# recommendation_runs recommendation_decisions
# system_actions      push_policies
# push_events         knowledge_assets
```

## 二、功能测试

### 2.1 运行自动化测试脚本

```bash
# 确保后端已启动
python tests/test_upgrade_features.py
```

测试覆盖：
- 健康检查
- 记忆 API（创建、查询、列表、确认、删除、统计）
- 推荐 API（运行推荐、最新推荐、推荐影响）
- 推送 API（创建策略、列表、状态、更新）
- 资产 API（列表资产）
- 飞书命令解析（help、memory、why）
- 服务层（MemoryService、RecommendationService、PushService、AssetService）

### 2.2 手动 API 测试

#### 记忆管理

```bash
# 创建记忆
curl -X POST http://localhost:8000/memories \
  -H "Content-Type: application/json" \
  -d '{"memory_type":"user","subject":"interest","content":"重点关注AI Agent","scope":"user","importance":0.8}'

# 查询记忆列表
curl "http://localhost:8000/memories?memory_type=user&limit=10"

# 查看记忆统计
curl http://localhost:8000/memories/profile/summary

# 导入用户画像到记忆
curl -X POST http://localhost:8000/memories/import-profile
```

#### 推荐系统

```bash
# 运行推荐
curl -X POST http://localhost:8000/recommendations/run \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"manual"}'

# 查看候选解释（替换为实际 candidate_id）
curl http://localhost:8000/recommendations/{candidate_id}/explain

# 提交反馈
curl -X POST http://localhost:8000/recommendations/{candidate_id}/feedback \
  -H "Content-Type: application/json" \
  -d '{"feedback_type":"confirm"}'
```

#### 推送策略

```bash
# 创建推送策略
curl -X POST http://localhost:8000/push/policies \
  -H "Content-Type: application/json" \
  -d '{"id":"daily_digest","name":"每日简报","trigger_type":"daily","max_per_day":5}'

# 查看推送状态
curl http://localhost:8000/push/status

# 查看推送事件
curl "http://localhost:8000/push/events?limit=10"
```

#### 多模态资产

```bash
# 上传图片/PDF
curl -X POST http://localhost:8000/assets/upload \
  -F "file=@/path/to/your/image.png"

# 查看资产列表
curl http://localhost:8000/assets

# 查看单个资产
curl http://localhost:8000/assets/{asset_id}
```

## 三、飞书命令测试

在飞书单聊中发送以下命令：

```
/omka help                    # 查看帮助（应包含记忆、推荐、推送、资产命令）
/omka memory list             # 查看记忆列表
/omka memory profile          # 查看记忆统计
/omka memory add 测试记忆内容  # 添加记忆
/omka why candidate:xxx       # 查询推荐原因
/omka source list             # 查看信息源
/omka push status             # 查看推送状态
/omka assets                  # 查看资产列表
```

## 四、UI 设置页面测试

启动前端后访问 http://localhost:5173/settings，验证以下新板块：

1. **排序权重** - 可调整兴趣/项目/新鲜度/热度权重
2. **推荐系统** - 可开关推荐、解释、反馈学习
3. **推送策略** - 可配置高价值阈值、每日上限、安静时间
4. **记忆系统** - 可开关记忆抽取、调整置信度阈值
5. **多模态资产** - 可配置文件大小限制、允许的文件类型

点击各板块的「保存」按钮，确认配置能写入数据库。

## 五、环境变量配置

新增环境变量已写入 `.env.example`，如需调整：

```bash
# 推荐系统
RECOMMENDATION_ENABLED=true
RECOMMENDATION_EXPLANATION_ENABLED=true
RECOMMENDATION_FEEDBACK_LEARNING_ENABLED=true

# 推送策略
PUSH_HIGH_SCORE_THRESHOLD=0.85
PUSH_MAX_PER_DAY=5
PUSH_QUIET_HOURS_START=22
PUSH_QUIET_HOURS_END=8

# 记忆系统
MEMORY_EXTRACTION_ENABLED=true
MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD=0.8
MEMORY_MAX_ACTIVE_ITEMS=20

# 多模态资产
ASSET_MAX_FILE_SIZE_MB=10
ASSET_ALLOWED_IMAGE_TYPES=jpg,jpeg,png,webp
ASSET_ALLOWED_DOCUMENT_TYPES=pdf,md,txt
```

## 五、常见问题排查

### 5.1 数据库表未创建

```bash
# 删除旧数据库重新创建
rm data/db/app.sqlite
python -m omka.app.main  # 启动时会自动创建所有表
```

### 5.2 飞书命令无响应

1. 检查 `FEISHU_ENABLED=true`
2. 检查 `FEISHU_AGENT_CONVERSATION_ENABLED=true`
3. 查看日志 `logs/omka.log` 中的飞书事件处理记录

### 5.3 推荐解释为空

需要先运行推荐：
```bash
curl -X POST http://localhost:8000/recommendations/run
```

### 5.4 资产上传失败

检查 `data/assets/` 目录是否存在且有写入权限：
```bash
ls -la data/assets/
```

## 六、提交记录

```bash
# 查看本次升级的所有提交
git log --oneline -10
```

应包含：
- Phase 0: 基础治理与编码清理
- Phase 1: 统一记忆内核
- Phase 2: 推荐解释与反馈学习
- Phase 3-5: Agent 执行通道、主动推送、多模态资产
