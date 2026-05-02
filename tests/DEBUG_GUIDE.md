# OMKA 调试测试指南

## 环境准备

### 1. 启动后端

```bash
# 安装依赖
pip install -r requirements.txt

# 复制配置模板
copy .env.example .env

# 编辑 .env 填入必要配置（GitHub Token、LLM 配置等）

# 启动服务
python -m omka.app.main
```

后端将在 http://localhost:8000 启动，API 文档: http://localhost:8000/docs

### 2. 启动前端（开发模式）

```bash
cd frontend
npm install
npm run dev
```

前端将在 http://localhost:5173 启动

### 3. 生产构建验证

```bash
cd frontend
npm run build
```

## 功能测试

### Phase 0-2 测试

```bash
# 基础 API 测试
python tests/test_api.py
```

### Phase 3 测试（Feishu Agent 权限管理）

```bash
python tests/test_phase3.py
```

测试覆盖：
- PermissionService 三层权限模型
- SourceActionService CRUD
- CandidateActionService 状态管理
- ConfigActionService 敏感配置保护
- KnowledgeActionService 搜索和删除
- ActionService 审计记录

### Phase 4-6 测试（前端页面 + API）

```bash
python tests/test_phase4_6.py
```

测试覆盖：
- Push Policy API（策略管理）
- Asset API（资产上传/管理）
- Memory API（记忆管理）
- 前端新页面可访问性

## 手动测试清单

### 信息源管理 (/sources)
- [ ] 查看信息源列表
- [ ] 添加新的 GitHub 仓库
- [ ] 添加新的搜索关键词
- [ ] 运行单个信息源
- [ ] 删除信息源

### 候选池 (/read-later)
- [ ] 查看候选条目
- [ ] 确认入库
- [ ] 忽略条目
- [ ] 提交反馈

### 知识库 (/knowledge)
- [ ] 查看已确认的知识
- [ ] 搜索知识
- [ ] 删除知识条目

### 推送管理 (/push)
- [ ] 查看推送策略列表
- [ ] 创建新策略
- [ ] 启用/禁用策略
- [ ] 查看推送历史

### 资产管理 (/assets)
- [ ] 查看资产列表
- [ ] 上传文件
- [ ] 按类型筛选
- [ ] 归档资产

### 记忆管理 (/memory)
- [ ] 查看记忆列表
- [ ] 创建新记忆
- [ ] 确认候选记忆
- [ ] 拒绝候选记忆
- [ ] 导入用户画像

### 设置 (/settings)
- [ ] 配置 GitHub Token
- [ ] 配置 LLM
- [ ] 配置飞书机器人
- [ ] 配置权限管理（admin/operator）
- [ ] 测试连接

### 仪表盘 (/)
- [ ] 查看统计信息
- [ ] 查看最近任务

## 飞书集成测试

### Webhook 推送
```bash
# 测试飞书连接
curl -X POST http://localhost:8000/settings/test-feishu

# 手动触发推送
curl -X POST http://localhost:8000/digests/run-today
```

### 飞书 Agent 命令
在飞书群聊或私聊中发送：
- `/omka help` - 查看帮助
- `/omka status` - 查看系统状态
- `/omka source list` - 查看信息源
- `/omka candidate list` - 查看候选池
- `/omka config list` - 查看配置
- `/omka knowledge search <关键词>` - 搜索知识

## 常见问题排查

### 后端启动失败
1. 检查 `.env` 配置是否正确
2. 检查端口 8000 是否被占用
3. 查看 `logs/omka.log` 错误日志

### 前端构建失败
1. 检查 Node.js 版本（需 18+）
2. 删除 `node_modules` 重新安装
3. 检查类型错误：`npm run build` 会显示具体错误

### API 请求失败
1. 确认后端是否运行
2. 检查 API 路径是否正确
3. 查看后端日志中的错误信息

### 数据库问题
```bash
# 查看数据库
sqlite3 data/db/app.sqlite

# 常用查询
.tables
SELECT * FROM source_configs;
SELECT * FROM candidates ORDER BY score DESC LIMIT 10;
SELECT * FROM push_policies;
SELECT * FROM knowledge_assets;
SELECT * FROM memory_items;
```

## 性能测试

```bash
# 测试并发请求
ab -n 1000 -c 10 http://localhost:8000/health

# 测试 API 响应时间
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/sources
```

## 日志查看

```bash
# 实时查看日志
tail -f logs/omka.log

# 查看错误日志
grep ERROR logs/omka.log

# 查看飞书相关日志
grep -i feishu logs/omka.log
```

## 部署检查清单

- [ ] 所有测试通过
- [ ] 前端构建成功
- [ ] 环境变量配置完整
- [ ] 数据库迁移完成
- [ ] 日志目录可写
- [ ] 数据目录可写
