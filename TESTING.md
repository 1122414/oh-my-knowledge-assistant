# OMKA 测试与调试指南

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env 填入 GITHUB_TOKEN 和 LLM 相关配置
```

### 2. 启动服务

```bash
# 方式一：直接运行
python -m uvicorn omka.app.main:app --reload --host 0.0.0.0 --port 8000

# 方式二：使用脚本
python -c "import uvicorn; uvicorn.run('omka.app.main:app', reload=True)"
```

服务启动后会自动：
- 初始化 SQLite 数据库（data/db/app.sqlite）
- 启动 APScheduler 调度器
- 注册每日定时任务（默认每天 9:00）

### 3. 运行功能测试

```bash
# 确保服务已在运行，然后执行
python tests/test_api.py
```

测试脚本会依次验证：
1. 健康检查接口
2. 数据源 CRUD
3. 手动触发抓取
4. 候选池查看
5. 排序执行
6. 候选确认入库
7. 知识库查看
8. 每日简报生成
9. 清理测试数据

## API 端点速查

### 系统
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /health | 健康检查 |

### 信息源
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /sources | 列出所有数据源 |
| POST | /sources | 创建数据源 |
| PUT | /sources/{id} | 更新数据源 |
| DELETE | /sources/{id} | 删除数据源 |
| POST | /sources/{id}/run | 手动触发抓取 |

### 候选池
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /candidates | 列出候选条目 |
| POST | /candidates/{id}/confirm | 确认入库 |
| POST | /candidates/{id}/ignore | 忽略 |
| POST | /candidates/{id}/feedback | 反馈 |

### 每日简报
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /digests/run-ranking | 执行排序 |
| GET | /digests/ranked | 查看排名结果 |
| POST | /digests/run-today | 手动生成今日简报 |

### 知识库
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /knowledge | 列出知识条目 |
| GET | /knowledge/{id} | 查看详情 |
| POST | /knowledge | 创建条目 |
| DELETE | /knowledge/{id} | 删除条目 |

## 调试技巧

### 查看日志
```bash
# 实时查看日志
tail -f logs/omka.log

# Windows
type logs\omka.log
```

### 查看数据库
```bash
# 使用 SQLite CLI
sqlite3 data/db/app.sqlite

# 查看表结构
.schema

# 查看数据源
SELECT * FROM source_configs;

# 查看抓取记录
SELECT * FROM fetch_runs ORDER BY started_at DESC;

# 查看候选池
SELECT id, title, score, status FROM candidate_items ORDER BY score DESC;
```

### 手动触发每日任务
```bash
# 通过 API 触发
curl -X POST http://localhost:8000/digests/run-today

# 或通过 Python 脚本
python -c "
import asyncio
from omka.app.services.daily_job import run_daily_job
result = asyncio.run(run_daily_job())
print(result)
"
```

### 测试单个数据源
```bash
# 先创建一个数据源，然后手动触发
curl -X POST http://localhost:8000/sources \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test_langgraph",
    "source_type": "github",
    "name": "LangGraph",
    "mode": "repo",
    "repo_full_name": "langchain-ai/langgraph",
    "enabled": true
  }'

curl -X POST http://localhost:8000/sources/test_langgraph/run
```

## 常见问题

### Q: 抓取返回 0 条数据
- 检查 `.env` 中 `GITHUB_TOKEN` 是否配置
- 检查网络是否能访问 GitHub API
- 查看日志中的错误信息

### Q: LLM 摘要失败
- 检查 `.env` 中 LLM 相关配置
- 如果使用 Ollama，确保本地服务已启动
- 摘要失败不会阻断主流程，会降级为简单摘要

### Q: 数据库锁定
- SQLite 不支持高并发写入
- 确保只有一个进程访问数据库

### Q: 定时任务不执行
- 检查调度器是否启动（查看日志）
- 检查 Cron 表达式是否正确
- 检查时区设置

## 文件结构

```
data/
  db/app.sqlite          # SQLite 数据库
  digests/YYYY-MM-DD.md  # 每日简报
  knowledge/github/      # 知识库 Markdown
  profiles/              # 用户画像配置
  raw/github/            # 原始数据（预留）
logs/omka.log            # 应用日志
```

## 扩展开发

### 添加新的信息源
1. 继承 `SourceConnector` 基类
2. 实现 `fetch()` 和 `normalize()` 方法
3. 在 `fetcher.py` 中使用新的 Connector

### 调整排序权重
编辑 `.env` 中的权重配置：
```env
SCORE_WEIGHT_INTEREST=0.40
SCORE_WEIGHT_PROJECT=0.30
SCORE_WEIGHT_FRESHNESS=0.15
SCORE_WEIGHT_POPULARITY=0.15
```

### 调整用户兴趣
编辑 `data/profiles/interests.yaml` 和 `projects.yaml`
