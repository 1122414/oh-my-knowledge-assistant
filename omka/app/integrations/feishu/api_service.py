import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    BatchCreateAppTableRecordRequest,
    BatchCreateAppTableRecordRequestBody,
    CreateAppRequest,
    CreateAppTableRequest,
    CreateAppTableRequestBody,
    ReqApp,
    ReqTable,
)
from lark_oapi.api.docx.v1 import (
    CreateDocumentRequest,
    CreateDocumentRequestBody,
    RawContentDocumentRequest,
)
from omka.app.core.logging import logger
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.errors import FeishuApiError


class FeishuApiService:
    """飞书开放平台统一 API 服务

    基于 lark-oapi SDK 封装，自动管理 tenant_access_token。
    为每个飞书能力提供独立的方法接口。

    使用方式:
        config = FeishuConfig(app_id="...", app_secret="...")
        svc = FeishuApiService(config)
        result = await svc.create_document("标题", "内容")
    """

    def __init__(self, config: FeishuConfig):
        self._config = config
        self._client = (
            lark.Client.builder()
            .app_id(config.app_id)
            .app_secret(config.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
        logger.info("FeishuApiService 初始化完成")

    @property
    def client(self) -> lark.Client:
        return self._client

    async def create_document(
        self,
        title: str,
        content: str,
        folder_token: str = "",
    ) -> dict:
        """创建飞书云文档并写入内容，返回 doc_id 和 url"""
        create_req = (
            CreateDocumentRequest.builder()
            .request_body(
                CreateDocumentRequestBody.builder()
                .title(title)
                .folder_token(folder_token or None)
                .build()
            )
            .build()
        )
        create_resp = await self._client.docx.v1.document.acreate(create_req)
        if create_resp.code != 0:
            raise FeishuApiError(f"创建文档失败: {create_resp.msg}", str(create_resp.code))

        doc_id = create_resp.data.document.document_id
        doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"

        if content:
            blocks_json = _build_content_json(content)
            if not blocks_json:
                raise FeishuApiError(
                    f"文档内容解析失败: markdown转为空blocks | content_len={len(content)}",
                    "EMPTY_BLOCKS",
                )
            chunk_size = 50
            for batch_idx in range(0, len(blocks_json), chunk_size):
                chunk = blocks_json[batch_idx:batch_idx + chunk_size]
                req = (
                    lark.BaseRequest.builder()
                    .http_method(lark.HttpMethod.POST)
                    .uri(f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children")
                    .token_types({lark.AccessTokenType.TENANT})
                    .body({"children": chunk, "index": -1})
                    .build()
                )
                resp = self._client.request(req)
                if resp.code != 0:
                    raise FeishuApiError(
                        f"文档内容写入失败(批次{batch_idx // chunk_size + 1}): {resp.msg} | "
                        f"blocks_count={len(blocks_json)} | chunk={len(chunk)}",
                        str(resp.code),
                    )

        logger.info("飞书文档创建成功 | doc_id=%s | title=%s | content_len=%d", doc_id, title, len(content) if content else 0)
        return {"doc_id": doc_id, "url": doc_url}

    async def get_document_raw_content(self, doc_id: str) -> str:
        """获取文档纯文本内容"""
        req = RawContentDocumentRequest.builder().document_id(doc_id).build()
        resp = await self._client.docx.v1.document.raw_content.aget(req)
        if resp.code != 0:
            raise FeishuApiError(f"读取文档失败: {resp.msg}", str(resp.code))
        return resp.data.content

    async def create_base(self, name: str, folder_token: str = "") -> dict:
        """创建多维表格，返回 app_token 和 url"""
        req = (
            CreateAppRequest.builder()
            .request_body(
                ReqApp.builder()
                .name(name)
                .folder_token(folder_token or None)
                .build()
            )
            .build()
        )
        resp = await self._client.bitable.v1.app.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建多维表格失败: {resp.msg}", str(resp.code))

        app_token = resp.data.app.app_token
        url = f"https://bytedance.feishu.cn/base/{app_token}"
        logger.info("多维表格创建成功 | app_token=%s | name=%s", app_token, name)
        return {"app_token": app_token, "url": url}

    async def create_table_with_fields(
        self, app_token: str, name: str, fields: list[dict]
    ) -> str:
        """创建数据表并定义字段，返回 table_id"""
        from lark_oapi.api.bitable.v1 import AppTableCreateHeader

        headers = [
            AppTableCreateHeader.builder()
            .field_name(f["name"])
            .type(f["type"])
            .build()
            for f in fields
        ]
        req = (
            CreateAppTableRequest.builder()
            .app_token(app_token)
            .request_body(
                CreateAppTableRequestBody.builder()
                .table(
                    ReqTable.builder()
                    .name(name)
                    .default_view_name("Grid View")
                    .fields(headers)
                    .build()
                )
                .build()
            )
            .build()
        )
        resp = await self._client.bitable.v1.app_table.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建数据表失败: {resp.msg}", str(resp.code))
        return resp.data.table_id

    async def insert_records(
        self, app_token: str, table_id: str, records: list[dict]
    ) -> list[str]:
        """批量插入记录，返回 record_id 列表"""
        record_objs = [
            AppTableRecord.builder().fields(r).build() for r in records
        ]
        req = (
            BatchCreateAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .request_body(
                BatchCreateAppTableRecordRequestBody.builder()
                .records(record_objs)
                .build()
            )
            .build()
        )
        resp = await self._client.bitable.v1.app_table_record.batch_create.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"插入记录失败: {resp.msg}", str(resp.code))
        return [r.record_id for r in (resp.data.records or [])]

    async def create_spreadsheet(self, title: str, folder_token: str = "") -> dict:
        """创建电子表格，返回 spreadsheet_token 和 url"""
        from lark_oapi.api.sheets.v3 import CreateSpreadsheetRequest, Spreadsheet

        req = (
            CreateSpreadsheetRequest.builder()
            .request_body(
                Spreadsheet.builder()
                .title(title)
                .folder_token(folder_token or None)
                .build()
            )
            .build()
        )
        resp = await self._client.sheets.v3.spreadsheet.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建电子表格失败: {resp.msg}", str(resp.code))
        token = resp.data.spreadsheet.spreadsheet_token
        return {
            "spreadsheet_token": token,
            "url": f"https://bytedance.feishu.cn/sheets/{token}",
        }

    async def write_sheet_values(
        self, spreadsheet_token: str, sheet_range: str, values: list[list]
    ) -> None:
        """写入单元格值（raw API v2）"""
        req = (
            lark.BaseRequest.builder()
            .http_method(lark.HttpMethod.PUT)
            .uri(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values")
            .token_types({lark.AccessTokenType.TENANT})
            .body({"valueRange": {"range": sheet_range, "values": values}})
            .build()
        )
        resp = self._client.request(req)
        if resp.code != 0:
            raise FeishuApiError(f"写入表格失败: {resp.msg}", str(resp.code))

    async def read_sheet_values(
        self, spreadsheet_token: str, sheet_range: str
    ) -> list[list]:
        """读取单元格值（raw API v2）"""
        req = (
            lark.BaseRequest.builder()
            .http_method(lark.HttpMethod.GET)
            .uri(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_range}")
            .token_types({lark.AccessTokenType.TENANT})
            .build()
        )
        resp = self._client.request(req)
        if resp.code != 0:
            raise FeishuApiError(f"读取表格失败: {resp.msg}", str(resp.code))
        data = resp.json()
        return data.get("data", {}).get("valueRange", {}).get("values", [])

    async def get_user_info(self, open_id: str = "", user_id: str = "") -> dict:
        """获取飞书用户信息"""
        from lark_oapi.api.contact.v3 import GetUserRequest

        if open_id:
            req = GetUserRequest.builder().user_id(open_id).user_id_type("open_id").build()
        else:
            req = GetUserRequest.builder().user_id(user_id).user_id_type("user_id").build()
        resp = await self._client.contact.v3.user.aget(req)
        if resp.code != 0:
            raise FeishuApiError(f"获取用户信息失败: {resp.msg}", str(resp.code))
        user = resp.data.user
        return {
            "name": user.name,
            "avatar_url": user.avatar_url,
            "department_ids": user.department_ids,
            "open_id": user.open_id,
        }

    async def create_calendar_event(
        self,
        calendar_id: str,
        summary: str,
        description: str,
        start_timestamp: int,
        end_timestamp: int,
        need_notification: bool = True,
    ) -> dict:
        """创建日历事件"""
        from lark_oapi.api.calendar.v4 import (
            CalendarEvent,
            CreateCalendarEventRequest,
            TimeInfo,
        )

        req = (
            CreateCalendarEventRequest.builder()
            .calendar_id(calendar_id)
            .request_body(
                CalendarEvent.builder()
                .summary(summary)
                .description(description)
                .need_notification(need_notification)
                .start_time(
                    TimeInfo.builder()
                    .timestamp(str(start_timestamp))
                    .timezone("Asia/Shanghai")
                    .build()
                )
                .end_time(
                    TimeInfo.builder()
                    .timestamp(str(end_timestamp))
                    .timezone("Asia/Shanghai")
                    .build()
                )
                .build()
            )
            .build()
        )
        resp = await self._client.calendar.v4.calendar_event.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建日历事件失败: {resp.msg}", str(resp.code))
        return {"event_id": resp.data.event.event_id}

    async def list_calendars(self) -> list[dict]:
        """获取日历列表"""
        from lark_oapi.api.calendar.v4 import ListCalendarRequest

        req = ListCalendarRequest.builder().build()
        resp = await self._client.calendar.v4.calendar.alist(req)
        if resp.code != 0:
            raise FeishuApiError(f"获取日历列表失败: {resp.msg}", str(resp.code))
        return [
            {"calendar_id": c.calendar_id, "summary": c.summary}
            for c in (resp.data.calendar_list or [])
        ]

    async def create_task(
        self, summary: str, description: str = "", due_at: int = 0
    ) -> dict:
        """创建飞书任务（v2）"""
        from lark_oapi.api.task.v2 import CreateTaskRequest, Due, InputTask

        req = (
            CreateTaskRequest.builder()
            .user_id_type("open_id")
            .request_body(
                InputTask.builder()
                .summary(summary)
                .description(description or None)
                .due(
                    Due.builder()
                    .time(str(due_at))
                    .is_all_day(False)
                    .build()
                    if due_at
                    else None
                )
                .build()
            )
            .build()
        )
        resp = await self._client.task.v2.task.acreate(req)
        if resp.code != 0:
            raise FeishuApiError(f"创建任务失败: {resp.msg}", str(resp.code))
        return {"task_guid": resp.data.task.guid}

    async def list_wiki_spaces(self) -> list[dict]:
        """列出知识空间（raw API）"""
        req = (
            lark.BaseRequest.builder()
            .http_method(lark.HttpMethod.GET)
            .uri("/open-apis/wiki/v2/spaces")
            .token_types({lark.AccessTokenType.TENANT})
            .build()
        )
        resp = self._client.request(req)
        if resp.code != 0:
            raise FeishuApiError(f"获取知识空间列表失败: {resp.msg}", str(resp.code))
        data = resp.json()
        return data.get("data", {}).get("items", [])


def _build_content_json(content: str) -> list[dict]:
    """将 Markdown 内容解析为 Feishu docx block JSON 列表

    支持: 标题, 粗体, 链接, 行内代码, 无序/有序列表,
           分隔线, 引用, 待办事项, 正文段落
    """
    blocks: list[dict] = []
    lines = content.split("\n")

    bullet_group: list[str] = []
    in_quote = False
    quote_lines: list[str] = []

    def flush_bullets():
        nonlocal bullet_group
        if bullet_group:
            for bline in bullet_group:
                blocks.append({
                    "block_type": 12,
                    "bullet": {"elements": _parse_inline(bline)},
                })
            bullet_group = []

    def flush_quote():
        nonlocal in_quote, quote_lines
        if in_quote:
            text = " ".join(quote_lines)
            blocks.append({
                "block_type": 15,
                "quote": {"elements": _parse_inline(text)},
            })
            quote_lines = []
            in_quote = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_bullets()
            flush_quote()
            i += 1
            continue

        if stripped == "---":
            flush_bullets()
            flush_quote()
            blocks.append({"block_type": 22, "divider": {}})
            i += 1
            continue

        if stripped.startswith("> "):
            flush_bullets()
            in_quote = True
            quote_lines.append(stripped[2:].strip())
            i += 1
            continue

        if stripped.startswith("- [ ] ") or stripped.startswith("- [x] "):
            flush_bullets()
            flush_quote()
            text = stripped[6:].strip()
            blocks.append({
                "block_type": 17,
                "todo": {"elements": _parse_inline(text)},
            })
            i += 1
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_quote()
            bullet_group.append(stripped[2:].strip())
            i += 1
            continue

        if _is_ordered(stripped):
            flush_quote()
            text = _strip_ordered_prefix(stripped)
            blocks.append({
                "block_type": 12,
                "bullet": {"elements": _parse_inline(text)},
            })
            i += 1
            continue

        flush_bullets()
        flush_quote()

        block_type, field_name, content_text = _parse_block_type(line)
        blocks.append({
            "block_type": block_type,
            field_name: {"elements": _parse_inline(content_text)},
        })
        i += 1

    flush_bullets()
    flush_quote()
    return blocks


def _parse_block_type(line: str) -> tuple[int, str, str]:
    stripped = line.strip()
    if stripped.startswith("###"):
        return 5, "heading3", stripped[3:].strip()
    if stripped.startswith("##"):
        return 4, "heading2", stripped[2:].strip()
    if stripped.startswith("#"):
        return 3, "heading1", stripped[1:].strip()
    return 2, "text", stripped


def _is_ordered(line: str) -> bool:
    import re
    return bool(re.match(r"^\d+[.)]\s", line.strip()))


def _strip_ordered_prefix(line: str) -> str:
    import re
    return re.sub(r"^\d+[.)]\s", "", line.strip())


def _parse_inline(text: str) -> list[dict]:
    """解析行内格式: 粗体 **text**, 链接 [text](url), 行内代码 `code`

    返回 Feishu docx elements 列表
    """
    import re
    if not text:
        return [{"text_run": {"content": ""}}]

    token_pattern = re.compile(
        r"(\*\*(.+?)\*\*)|"        # bold
        r"(\[(.+?)\]\((.+?)\))|"   # link [text](url)
        r"(`(.+?)`)"               # inline code
    )

    elements: list[dict] = []
    pos = 0

    for m in token_pattern.finditer(text):
        if m.start() > pos:
            elements.append({"text_run": {"content": text[pos:m.start()]}})
        pos = m.end()

        if m.group(1):  # bold
            elements.append({"text_run": {
                "content": m.group(2),
                "text_element_style": {"bold": True},
            }})
        elif m.group(3):  # link
            elements.append({"text_run": {
                "content": m.group(4),
                "text_element_style": {"link": {"url": m.group(5)}},
            }})
        elif m.group(6):  # inline code
            elements.append({"text_run": {
                "content": m.group(7),
                "text_element_style": {"inline_code": True},
            }})

    if pos < len(text):
        elements.append({"text_run": {"content": text[pos:]}})

    return elements if elements else [{"text_run": {"content": text}}]


def build_feishu_api_service() -> FeishuApiService | None:
    """从全局配置构建 FeishuApiService（便捷工厂）"""
    from omka.app.core.settings_service import get_setting
    from omka.app.integrations.feishu.config import FeishuConfig

    config = FeishuConfig(
        enabled=get_setting("feishu_enabled", False),
        app_id=get_setting("feishu_app_id", ""),
        app_secret=get_setting("feishu_app_secret", ""),
        doc_folder_token=get_setting("feishu_doc_folder_token", ""),
        base_folder_token=get_setting("feishu_base_folder_token", ""),
        sheet_folder_token=get_setting("feishu_sheet_folder_token", ""),
        default_calendar_id=get_setting("feishu_default_calendar_id", ""),
    )
    if not config.is_configured():
        logger.warning("飞书未配置，无法创建 FeishuApiService")
        return None
    return FeishuApiService(config)
