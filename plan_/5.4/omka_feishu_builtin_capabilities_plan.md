# OMKA 飞书内置能力集成计划

**日期**: 2026-05-04 | **版本**: v1.0 | **状态**: 规划中
**前提**: OMKA 已有完整飞书应用机器人（11 文件，20+ 命令），`lark-oapi>=1.5.0` 已安装但仅用于 WebSocket。

---

## 目标

让 OMKA 飞书机器人具备调用飞书开放平台所有常用内置能力，使知识助手不仅仅是"问答 + 推送"，而是能操作飞书生态的智能 Agent。

### 能力优先矩阵

| 优先级 | 能力 | OMKA 场景 | 飞书 API 模块 |
|--------|------|-----------|-------------|
| P0 | 云文档 | 每日简报自动生成为飞书文档；Agent 对话结果保存为文档 | `docx/v1` |
| P0 | 多维表格 | 知识条目结构化存储到 Base；候选池导入表格管理 | `bitable/v1` |
| P1 | 电子表格 | 数据导出为 Sheet；排名/统计写入电子表格 | `sheets/v3` + v2 raw |
| P1 | 联系人 | 查询用户信息；@ 特定用户；权限校验增强 | `contact/v3` |
| P2 | 日历 | 定时任务日历提醒；知识回顾日程 | `calendar/v4` |
| P2 | 云空间/知识库 | 把知识库内容发布到飞书知识空间 | `wiki/v2`, `drive/v1` |
| P3 | 任务 | 候选条目转为待办任务；阅读提醒 | `task/v2` |
| P3 | 审批 | 知识入库审批流程 | `approval/v4` |
| P3 | 互动卡片 | 候选条目以卡片形式展示，按钮交互替代文本命令 | `im/v1` card |

---

## 核心架构决策

### 决策 1: 采用 `lark-oapi` REST Client 还是继续 httpx？

**现状**: 当前 `auth.py` 和 `client.py` 全部使用原始 `httpx.AsyncClient` + 手动 token 管理。

**推荐**: **渐进迁移到 `lark.Client`（typed SDK）**

理由：
- SDK 自动管理 `tenant_access_token` 生命周期（无需 `auth.py` 缓存逻辑）
- 类型安全的 Request/Response 模型，减少手写 JSON 序列化错误
- 同步/异步双模式: `.get()` / `.aget()` 
- 新能力全部用 SDK，旧 IM 客户端保持兼容运行
- `ws_client.py` 已经使用 SDK → 依赖冲突不存在

过渡方案：

```
新能力（docx/bitable/sheets/calendar/task/approval）
  → FeishuApiService (拥有 lark.Client 单例)
  → 使用 typed SDK: client.docx.v1.document.create(...)

旧能力（发消息/收消息）
  → FeishuAppBotClient (保持 httpx)
  → FeishuWebSocketClient (保持 lark_oapi.ws.Client)
  → 后续可逐步迁移到 SDK 的 im 模块
```

### 决策 2: 单一 Client 还是分离 Client？

**推荐**: **单一 `FeishuApiService`，方法按能力分组**

```python
class FeishuApiService:
    """统一飞书 API 服务，封装 lark.Client"""
    
    def __init__(self, config: FeishuConfig):
        self._client = lark.Client.builder()
            .app_id(config.app_id)
            .app_secret(config.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
    
    # 云文档
    async def create_document(self, title, content, folder_token=None) -> str
    async def get_document_content(self, doc_id) -> str
    async def update_document(self, doc_id, blocks) -> None
    
    # 多维表格
    async def create_base(self, name, folder_token=None) -> str
    async def create_table(self, app_token, name, fields) -> str
    async def insert_records(self, app_token, table_id, records) -> list
    
    # 电子表格
    async def create_spreadsheet(self, title) -> str
    async def write_sheet_values(self, token, range, values) -> None
    async def read_sheet_values(self, token, range) -> list
    
    # 联系人
    async def get_user_info(self, open_id) -> dict
    
    # 日历
    async def create_event(self, calendar_id, summary, start, end) -> str
    
    # 任务
    async def create_task(self, summary, due=None) -> str
```

不创建继承 `FeishuAppBotClient` 的子类，因为权限范围和接口形态完全不同。

### 决策 3: 权限管理方案

飞书开放平台的每个 API 能力需要独立开通权限（在开发者控制台申请）。OMKA 作为一个整体应用，开通以下权限集：

**权限清单（需在飞书开发者控制台逐个开通）**:

```
App 类型: 企业自建应用（内部应用）
获取凭证方式: tenant_access_token（应用身份）

基础权限（已有）:
  - im:message                   发送消息
  - im:message:readonly          接收消息

新增权限:
  - docx:document                创建/编辑云文档
  - docx:document:readonly       读取云文档
  - bitable:app                  创建/管理多维表格
  - bitable:app:readonly         读取多维表格
  - sheets:spreadsheet           写入电子表格
  - sheets:spreadsheet:readonly  读取电子表格
  - drive:drive                  上传文件
  - contact:user:readonly        读取用户信息
  - calendar:calendar            创建日历/日程
  - calendar:calendar:readonly   读取日历/日程
  - task:task:write              创建/管理任务
  - task:task:readonly           读取任务
  - approval:approval            创建审批实例
  - approval:approval:readonly   读取审批
  - wiki:wiki:readonly           读取知识空间
```

---

## 分阶段实施计划

### Phase 0: 基础设施（1-2h）

**目标**: 让 `lark.Client` 在 OMKA 服务中可用，验证连通性。

#### 0.1 创建 `api_service.py`

新建 `omka/app/integrations/feishu/api_service.py`:

```python
import lark_oapi as lark
from omka.app.core.logging import logger
from omka.app.integrations.feishu.config import FeishuConfig

class FeishuApiService:
    """飞书开放平台统一 API 服务
    
    基于 lark-oapi SDK 封装，自动管理 tenant_access_token。
    为每个飞书能力提供独立的方法接口。
    """
    
    def __init__(self, config: FeishuConfig):
        self._config = config
        self._client = lark.Client.builder() \
            .app_id(config.app_id) \
            .app_secret(config.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    
    @property
    def client(self) -> lark.Client:
        return self._client
```

#### 0.2 添加测试端点

在 `routes_feishu.py` 添加:

```python
@router.post("/test-api-service")
async def test_api_service():
    """测试 FeishuApiService 是否正常工作（获取用户列表验证）"""
    config = _build_feishu_config()
    if not config.is_configured():
        return {"ok": False, "error": "Feishu not configured"}
    
    svc = FeishuApiService(config)
    try:
        from lark_oapi.api.contact.v3 import ListUserRequest
        req = ListUserRequest.builder()
            .page_size(1).build()
        resp = svc.client.contact.v3.user.list(req)
        return {"ok": resp.code == 0, "code": resp.code, "msg": resp.msg}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

#### 验证方式

```bash
# 确保 .env 中 FEISHU_APP_ID 和 FEISHU_APP_SECRET 已配置
curl -X POST http://localhost:8000/integrations/feishu/test-api-service
# 期望: {"ok": true, ...}
```

**检查点**: `lark-oapi` SDK 能成功获取 tenant_access_token 并调用飞书 API。

---

### Phase 1: P0 能力 — 云文档 + 多维表格（4-6h）

这是最高优先级的两个能力，直接关联 OMKA 核心场景。

#### 1.1 云文档 (`api_service.py` 扩展)

```python
from lark_oapi.api.docx.v1 import *

class FeishuApiService:
    
    async def create_document(
        self,
        title: str,
        content: str,
        folder_token: str = "",
    ) -> dict:
        """创建飞书云文档，返回 doc_id 和 url"""
        # 1. 创建空文档
        create_req = CreateDocumentRequest.builder() \
            .request_body(CreateDocumentRequestBody.builder()
                          .title(title)
                          .folder_token(folder_token or None)
                          .build()) \
            .build()
        create_resp = await self._client.docx.v1.document.acreate(create_req)
        if create_resp.code != 0:
            raise FeishuApiError(f"创建文档失败: {create_resp.msg}")
        
        doc_id = create_resp.data.document.document_id
        doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"
        
        # 2. 写入内容（分段落）
        if content:
            paragraphs = content.split("\n\n")
            blocks = []
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                block_type = 11 if para.startswith("###") else \
                             9  if para.startswith("##") else \
                             3  if para.startswith("#")  else 2
                text = para.lstrip("#").strip()
                blocks.append(_make_text_block(text, block_type))
            
            if blocks:
                block_req = CreateDocumentBlockChildrenRequest.builder() \
                    .document_id(doc_id) \
                    .block_id(doc_id) \
                    .request_body(CreateDocumentBlockChildrenRequestBody.builder()
                                  .children(blocks).build())
                    .build()
                await self._client.docx.v1.document_block.children.acreate(block_req)
        
        logger.info("飞书文档创建成功 | doc_id=%s | title=%s", doc_id, title)
        return {"doc_id": doc_id, "url": doc_url}
    
    async def get_document_raw_content(self, doc_id: str) -> str:
        """获取文档纯文本内容"""
        req = RawContentDocumentRequest.builder().document_id(doc_id).build()
        resp = await self._client.docx.v1.document.raw_content.aget(req)
        if resp.code != 0:
            raise FeishuApiError(f"读取文档失败: {resp.msg}")
        return resp.data.content


def _make_text_block(text: str, block_type: int = 2):
    """构造 docx Block（文本段落）"""
    return Block.builder() \
        .block_type(block_type) \
        .text(Text.builder()
              .elements([TextElement.builder()
                        .text_run(TextRun.builder().content(text).build())
                        .build()])
              .build()) \
        .build()
```

#### 1.2 多维表格 (`api_service.py` 扩展)

```python
from lark_oapi.api.bitable.v1 import *

class FeishuApiService:
    
    async def create_base(
        self, name: str, folder_token: str = ""
    ) -> dict:
        """创建多维表格（Base），返回 app_token 和 url"""
        req = CreateAppRequest.builder() \
            .request_body(ReqApp.builder()
                          .name(name)
                          .folder_token(folder_token or None)
                          .build())
            .build()
        resp = await self._client.bitable.v1.app.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建多维表格失败: {resp.msg}")
        
        app_token = resp.data.app.app_token
        url = f"https://bytedance.feishu.cn/base/{app_token}"
        return {"app_token": app_token, "url": url}
    
    async def create_table_with_fields(
        self, app_token: str, name: str, fields: list[dict]
    ) -> str:
        """创建数据表，返回 table_id。
        
        fields: [{"name": "标题", "type": 1}, {"name": "分数", "type": 2}, ...]
        type: 1=文本, 2=数字, 5=日期, 4=复选框
        """
        headers = [
            AppTableCreateHeader.builder()
                .field_name(f["name"]).type(f["type"]).build()
            for f in fields
        ]
        req = CreateAppTableRequest.builder() \
            .app_token(app_token) \
            .request_body(CreateAppTableRequestBody.builder()
                          .table(ReqTable.builder()
                                 .name(name)
                                 .default_view_name("Grid View")
                                 .fields(headers).build())
                          .build())
            .build()
        resp = await self._client.bitable.v1.app_table.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建数据表失败: {resp.msg}")
        return resp.data.table_id
    
    async def insert_records(
        self, app_token: str, table_id: str, records: list[dict]
    ) -> list[str]:
        """批量插入记录，返回 record_id 列表"""
        record_objs = [
            AppTableRecord.builder().fields(r).build() for r in records
        ]
        req = BatchCreateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(BatchCreateAppTableRecordRequestBody.builder()
                          .records(record_objs).build())
            .build()
        resp = await self._client.bitable.v1.app_table_record.batch_create.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"插入记录失败: {resp.msg}")
        return [r.record_id for r in (resp.data.records or [])]
```

#### 1.3 命令集成

在 `command_router.py` 中添加新命令（约 150 行）:

```python
# 注册新命令类型
class FeishuCommandType(str, Enum):
    DOC = "doc"       # 新增
    BASE = "base"     # 新增
    # ... 已有命令类型

# 在 handlers 字典中注册
handlers["doc"] = _handle_doc
handlers["base"] = _handle_base

# HELP_TEXT 添加
/omka doc create <标题> [内容] — 创建飞书云文档
/omka doc digest — 将最新简报保存为云文档
/omka base create <名称> — 创建多维表格
/omka base import — 将知识库导入多维表格
```

**核心命令场景**:

| 命令 | 功能 | 实现 |
|------|------|------|
| `/omka doc digest` | 把最新 briefing 生成飞书文档 | `_handle_doc_digest()` → 读取 latest digest markdown → `create_document()` |
| `/omka doc create <标题>` | 创建空白文档 | `_handle_doc_create()` → `create_document(title, "")` |
| `/omka base import` | 知识库导入多维表格 | `_handle_base_import()` → `create_base()` → `create_table_with_fields()` → `insert_records()` |

#### 验证方式

```bash
# 1. 测试云文档创建
curl -X POST http://localhost:8000/integrations/feishu/test-doc \
  -H "Content-Type: application/json" \
  -d '{"title": "OMKA 测试", "content": "# 标题\n\n这是内容"}'
# 期望: {"ok": true, "doc_id": "...", "url": "..."}

# 2. 通过飞书机器人命令测试
# 在飞书中对机器人发送:
/omka doc create 测试文档 这是我的第一个飞书文档

# 3. 测试多维表格
/omka base import
# 期望: 知识库条目导入到新的多维表格中
```

**检查点**: 
- [ ] 机器人能创建云文档，用户能在飞书中打开
- [ ] 每日简报能一键转存为云文档（含标题、摘要、链接）
- [ ] 知识库能一键导入多维表格（含标题、摘要、分数、日期字段）

---

### Phase 2: P1 能力 — 电子表格 + 联系人（3-4h）

#### 2.1 电子表格 (`api_service.py` 扩展)

飞书电子表格分两个 API 版本:
- **v3**: 元数据操作（创建、查询 sheet 列表）— typed SDK
- **v2**: 单元格读写 — 需用 raw `BaseRequest`

```python
from lark_oapi.api.sheets.v3 import *

class FeishuApiService:
    
    async def create_spreadsheet(self, title: str, folder_token: str = "") -> dict:
        """创建电子表格"""
        req = CreateSpreadsheetRequest.builder() \
            .request_body(Spreadsheet.builder()
                          .title(title)
                          .folder_token(folder_token or None)
                          .build())
            .build()
        resp = await self._client.sheets.v3.spreadsheet.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建电子表格失败: {resp.msg}")
        token = resp.data.spreadsheet.spreadsheet_token
        return {"spreadsheet_token": token, 
                "url": f"https://bytedance.feishu.cn/sheets/{token}"}
    
    async def write_sheet_values(
        self, spreadsheet_token: str, sheet_range: str, values: list[list]
    ) -> None:
        """写入单元格（使用 raw API v2）"""
        req = lark.BaseRequest.builder() \
            .http_method(lark.HttpMethod.PUT) \
            .uri(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values") \
            .token_types({lark.AccessTokenType.TENANT}) \
            .body({"valueRange": {"range": sheet_range, "values": values}}) \
            .build()
        resp = self._client.request(req)
        if resp.code != 0:
            raise FeishuApiError(f"写入表格失败: {resp.msg}")
    
    async def read_sheet_values(
        self, spreadsheet_token: str, sheet_range: str
    ) -> list[list]:
        """读取单元格（使用 raw API v2）"""
        req = lark.BaseRequest.builder() \
            .http_method(lark.HttpMethod.GET) \
            .uri(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_range}") \
            .token_types({lark.AccessTokenType.TENANT}) \
            .build()
        resp = self._client.request(req)
        if resp.code != 0:
            raise FeishuApiError(f"读取表格失败: {resp.msg}")
        return resp.json().get("data", {}).get("valueRange", {}).get("values", [])
```

#### 2.2 联系人

```python
from lark_oapi.api.contact.v3 import *

class FeishuApiService:
    
    async def get_user_info(self, open_id: str = "", user_id: str = "") -> dict:
        """获取用户信息（飞书姓名、头像、部门等）"""
        if open_id:
            req = GetUserRequest.builder().user_id(open_id).user_id_type("open_id").build()
        else:
            req = GetUserRequest.builder().user_id(user_id).user_id_type("user_id").build()
        resp = await self._client.contact.v3.user.aget(req)
        if resp.code != 0:
            raise FeishuApiError(f"获取用户信息失败: {resp.msg}")
        user = resp.data.user
        return {
            "name": user.name,
            "avatar_url": user.avatar_url,
            "department_ids": user.department_ids,
            "open_id": user.open_id,
        }
```

#### 2.3 命令集成

| 命令 | 功能 |
|------|------|
| `/omka sheet export candidates` | 候选池导出为电子表格 |
| `/omka sheet export knowledge` | 知识库导出为电子表格 |
| `/omka whoami` | 显示当前用户的飞书身份信息 |

---

### Phase 3: P2 能力 — 日历 + 知识空间（3-4h）

#### 3.1 日历

```python
from lark_oapi.api.calendar.v4 import *

class FeishuApiService:
    
    async def create_event(
        self, calendar_id: str, summary: str, description: str,
        start_timestamp: int, end_timestamp: int,
        need_notification: bool = True,
    ) -> dict:
        """创建日历事件"""
        req = CreateCalendarEventRequest.builder() \
            .calendar_id(calendar_id) \
            .request_body(CalendarEvent.builder()
                          .summary(summary)
                          .description(description)
                          .need_notification(need_notification)
                          .start_time(TimeInfo.builder()
                                      .timestamp(str(start_timestamp))
                                      .timezone("Asia/Shanghai").build())
                          .end_time(TimeInfo.builder()
                                    .timestamp(str(end_timestamp))
                                    .timezone("Asia/Shanghai").build())
                          .build())
            .build()
        resp = await self._client.calendar.v4.calendar_event.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建日历事件失败: {resp.msg}")
        return {"event_id": resp.data.event.event_id}
    
    async def list_primary_calendars(self) -> list[dict]:
        """获取主日历列表"""
        req = ListCalendarRequest.builder().build()
        resp = await self._client.calendar.v4.calendar.alist(req)
        if resp.code != 0:
            raise FeishuApiError(f"获取日历列表失败: {resp.msg}")
        return [
            {"calendar_id": c.calendar_id, "summary": c.summary}
            for c in (resp.data.calendar_list or [])
        ]
```

#### 3.2 知识空间

```python
# Wiki v2 和 Drive v1 使用 raw API（lark-oapi 的 typed SDK 暂不完整）

class FeishuApiService:
    
    async def list_wiki_spaces(self) -> list[dict]:
        """列出知识空间"""
        req = lark.BaseRequest.builder() \
            .http_method(lark.HttpMethod.GET) \
            .uri("/open-apis/wiki/v2/spaces") \
            .token_types({lark.AccessTokenType.TENANT}) \
            .build()
        resp = self._client.request(req)
        data = resp.json()
        return data.get("data", {}).get("items", [])
```

#### 3.3 命令集成

| 命令 | 功能 |
|------|------|
| `/omka calendar review 9:00` | 创建"每日知识回顾"日历提醒 |
| `/omka calendar digest` | 将简报同步为日历事件 |
| `/omka wiki list` | 列出知识空间 |
| `/omka wiki publish <doc_id>` | 将文档发布到知识空间 |

---

### Phase 4: P3 能力 — 任务 + 审批 + 互动卡片（4-6h）

#### 4.1 任务

```python
from lark_oapi.api.task.v2 import *

class FeishuApiService:
    
    async def create_task(
        self, summary: str, description: str = "", due_at: int = 0
    ) -> dict:
        """创建飞书任务"""
        req = CreateTaskRequest.builder() \
            .user_id_type("open_id") \
            .request_body(InputTask.builder()
                          .summary(summary)
                          .description(description or None)
                          .due(Due.builder()
                               .time(str(due_at)).is_all_day(False).build()
                               if due_at else None)
                          .build())
            .build()
        resp = await self._client.task.v2.task.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建任务失败: {resp.msg}")
        return {"task_guid": resp.data.task.guid}
```

#### 4.2 互动卡片

飞书互动卡片使用 JSON DSL 构建，与当前 `send_post` 不同:

```python
class FeishuAppBotClient:
    
    async def send_interactive_card(
        self, receive_id: str, card_json: dict, receive_id_type: str = "chat_id"
    ) -> FeishuSendResult:
        """发送互动卡片消息"""
        content = json.dumps(card_json, ensure_ascii=False)
        payload = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": content,
        }
        url = f"{self._base_url}/im/v1/messages?receive_id_type={receive_id_type}"
        return await self._request_with_retry(url, payload)
```

候选卡片示例:

```json
{
  "header": {
    "title": {"tag": "plain_text", "content": "🔗 LangGraph v0.3 Release"},
    "template": "blue"
  },
  "elements": [
    {"tag": "div", "text": {"tag": "lark_md", "content": "**New**: State management API for complex agent graphs."}},
    {"tag": "hr"},
    {"tag": "action", "actions": [
      {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 入库"}, "type": "primary", "value": "{\"action\":\"confirm\",\"id\":\"c_123\"}"},
      {"tag": "button", "text": {"tag": "plain_text", "content": "📖 稍后阅读"}, "type": "default", "value": "{\"action\":\"later\",\"id\":\"c_123\"}"},
      {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 忽略"}, "type": "danger", "value": "{\"action\":\"ignore\",\"id\":\"c_123\"}"}
    ]}
  ]
}
```

卡片按钮回调需要在 `event_handler.py` 中处理 `card.action.trigger` 事件:

```python
from lark_oapi.api.im.v1 import P2CardActionTriggerV1

# 在 ws_client.py 中注册
event_handler = lark.EventDispatcherHandler.builder() \
    .register_p2_im_message_receive_v1(handle_message) \
    .register_p2_card_action_trigger(handle_card_action) \
    .build()

def handle_card_action(data: P2CardActionTriggerV1) -> None:
    """处理卡片按钮点击"""
    action_value = json.loads(data.event.action.value)
    # 根据 action 类型执行对应操作
    # 更新卡片内容（显示操作结果）
```

#### 4.3 命令集成

| 命令 | 功能 |
|------|------|
| `/omka task add <内容>` | 将候选条目转为飞书任务 |
| `/omka candidate card` | 以卡片形式展示候选列表（替代长文本） |

---

## 实施总览

### 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `omka/app/integrations/feishu/api_service.py` | **新建** | 飞书 API 统一服务 (lark.Client 封装) |
| `omka/app/integrations/feishu/errors.py` | 修改 | 添加 `FeishuApiError` |
| `omka/app/integrations/feishu/command_router.py` | 修改 | 新增 doc/base/sheet/calendar/task 命令处理 |
| `omka/app/integrations/feishu/models.py` | 修改 | 扩展 `FeishuCommandType` 枚举 |
| `omka/app/integrations/feishu/client.py` | 修改 | 添加 `send_interactive_card()` |
| `omka/app/integrations/feishu/event_handler.py` | 修改 | 添加 card action 事件处理 |
| `omka/app/integrations/feishu/ws_client.py` | 修改 | 注册新事件类型 |
| `omka/app/api/routes_feishu.py` | 修改 | 添加测试端点 |
| `omka/app/core/config.py` | 修改 | 添加 `feishu_doc_folder_token` 配置 |

### 新依赖

无新增依赖。`lark-oapi>=1.5.0` 已在 `requirements.txt` 中。

### 权限开通（飞书开发者控制台）

共需开通约 15 个 API 权限（每个能力 2 个：读写权限各一）。

---

## 风险与注意事项

### 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| `lark-oapi` SDK 版本兼容 | SDK 升级可能破坏现有代码 | 固定版本 `lark-oapi>=1.5.0,<2.0.0`；新旧代码分离（新能力用 SDK，旧 IM 保持 httpx） |
| 飞书 API 限流 | 批量操作可能触发限流 | 每次批量插入限制 50 条；Base 单次最多 500 条 |
| 权限未开通 | 接口调用返回 403 | 在 Phase 0 中先验证 API 连通性 |
| `command_router.py` 膨胀 | 文件已达 1137 行 | 将每个能力的命令处理拆分为独立 handler 文件 |

### 飞书 API 限制

- 云文档 block 批量创建: 单次最多 50 个子 block，block 嵌套深度最大 100
- 多维表格: 单表字段数上限 100，单次 batch_create 最多 500 条
- 电子表格: v2 接口单次写入最多 5000 个单元格
- 日历: 创建事件需要 app 开通"机器人"能力

---

## 后续演进

1. **Webhook → WebSocket 全面迁移** (已基本完成)
2. **IM 客户端迁移到 SDK** (可选，后用): 将 `FeishuAppBotClient` 的 httpx 调用改为 `lark.Client.im.v1`
3. **AI Agent 自主调用飞书能力**: Agent 对话中理解"把这篇存入飞书文档"→ 自动调用 `FeishuApiService.create_document()`
4. **飞书云文档 → 知识源**: 反向读取飞书文档内容纳入知识库（需要 OCR + 结构解析）
5. **飞书生态联动**: 审批流 → 自动入库 → 生成文档 → 推送到群

---

## 验证清单

### Phase 0
- [ ] `lark.Client` 初始化成功
- [ ] `POST /integrations/feishu/test-api-service` 返回用户列表

### Phase 1
- [ ] 创建云文档（飞书可打开查看）
- [ ] 每日简报转存为云文档（含完整格式）
- [ ] 创建多维表格 + 插入知识条目
- [ ] `/omka doc digest` 和 `/omka base import` 飞书命令正常

### Phase 2
- [ ] 创建电子表格 + 写入候选数据
- [ ] 读取单元格数据
- [ ] 查询用户信息

### Phase 3
- [ ] 创建日历事件（含通知提醒）
- [ ] 列出知识空间

### Phase 4
- [ ] 创建飞书任务
- [ ] 发送互动卡片
- [ ] 卡片按钮点击事件处理
