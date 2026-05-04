"""Feishu Built-in Capabilities Integration Test

Covers:
  1. Module import verification
  2. FeishuConfig field validation
  3. FeishuApiService instantiation
  4. Command type (FeishuCommandType) completeness
  5. Card message method existence
  6. Exception class hierarchy
  7. lark-oapi SDK availability

Usage:
  python tests/test_feishu_capabilities.py

NOTE: Feishu API tests require valid FEISHU_APP_ID and FEISHU_APP_SECRET.
If not configured, they are skipped.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

passed = 0
failed = 0


def heading(title):
    print(f"\n==== {title} ====")


def mark_ok(label):
    return f"[OK] {label}"


def mark_fail(label):
    return f"[FAIL] {label}"


def check(condition, name):
    global passed, failed
    if condition:
        passed += 1
        print(f"  {mark_ok(name)}")
    else:
        failed += 1
        print(f"  {mark_fail(name)}")


def test_01_imports():
    heading("Module Import Verification")
    try:
        from omka.app.integrations.feishu.api_service import (
            FeishuApiService,
            build_feishu_api_service,
        )
        from omka.app.integrations.feishu.errors import (
            FeishuApiError,
            FeishuAuthError,
            FeishuConfigError,
            FeishuEventError,
            FeishuSendError,
        )
        from omka.app.integrations.feishu.models import (
            FeishuCommandType,
            FeishuCommandResult,
            FeishuSendResult,
            FeishuMessageEvent,
        )
        from omka.app.integrations.feishu.config import FeishuConfig
        from omka.app.integrations.feishu.client import FeishuAppBotClient

        check(True, "api_service.FeishuApiService")
        check(True, "api_service.build_feishu_api_service")
        check(True, "errors - 6 exception classes")
        check(True, "models - FeishuCommandType/Result")
        check(True, "config.FeishuConfig")
        check(True, "client.FeishuAppBotClient")
    except Exception as e:
        check(False, f"Import error: {e}")


def test_02_command_types():
    heading("Command Type Enum Completeness")
    try:
        from omka.app.integrations.feishu.models import FeishuCommandType

        expected = {
            "help", "bind", "status", "latest", "run", "chat",
            "source", "candidate", "config", "push", "knowledge",
            "doc", "base", "sheet", "calendar", "task", "unknown",
        }
        actual = set(ct.value for ct in FeishuCommandType)
        check(expected.issubset(actual), f"All command types present ({len(actual)} total)")
        check("doc" in actual, "DOC command registered")
        check("base" in actual, "BASE command registered")
        check("sheet" in actual, "SHEET command registered")
        check("calendar" in actual, "CALENDAR command registered")
        check("task" in actual, "TASK command registered")
    except Exception as e:
        check(False, f"Error: {e}")


def test_03_config_fields():
    heading("FeishuConfig Field Validation")
    try:
        from omka.app.integrations.feishu.config import FeishuConfig

        cfg = FeishuConfig(app_id="test", app_secret="test")
        check(cfg.doc_folder_token == "", "doc_folder_token default")
        check(cfg.base_folder_token == "", "base_folder_token default")
        check(cfg.sheet_folder_token == "", "sheet_folder_token default")
        check(cfg.default_calendar_id == "", "default_calendar_id default")
        check(cfg.is_configured(), "is_configured() returns True")

        masked = cfg.get_masked_config()
        check("doc_folder_token" in masked, "get_masked_config has doc_folder_token")
        check("base_folder_token" in masked, "get_masked_config has base_folder_token")
    except Exception as e:
        check(False, f"Error: {e}")


def test_04_api_service_init():
    heading("FeishuApiService Instantiation")
    try:
        from omka.app.integrations.feishu.config import FeishuConfig
        from omka.app.integrations.feishu.api_service import FeishuApiService

        cfg = FeishuConfig(app_id="test_id", app_secret="test_secret")
        svc = FeishuApiService(cfg)
        check(svc is not None, "FeishuApiService instantiated")
        check(svc.client is not None, "lark.Client built")
        check(hasattr(svc, "create_document"), "create_document method")
        check(hasattr(svc, "create_base"), "create_base method")
        check(hasattr(svc, "create_spreadsheet"), "create_spreadsheet method")
        check(hasattr(svc, "get_user_info"), "get_user_info method")
        check(hasattr(svc, "create_calendar_event"), "create_calendar_event method")
        check(hasattr(svc, "list_calendars"), "list_calendars method")
        check(hasattr(svc, "create_task"), "create_task method")
        check(hasattr(svc, "list_wiki_spaces"), "list_wiki_spaces method")
        check(hasattr(svc, "write_sheet_values"), "write_sheet_values method")
        check(hasattr(svc, "read_sheet_values"), "read_sheet_values method")
        check(hasattr(svc, "insert_records"), "insert_records method")
        check(hasattr(svc, "create_table_with_fields"), "create_table_with_fields method")
        check(hasattr(svc, "get_document_raw_content"), "get_document_raw_content method")
    except Exception as e:
        check(False, f"Error: {e}")


def test_05_client_card_support():
    heading("FeishuAppBotClient Interactive Card Support")
    try:
        from omka.app.integrations.feishu.config import FeishuConfig
        from omka.app.integrations.feishu.auth import FeishuAuthService
        from omka.app.integrations.feishu.client import FeishuAppBotClient

        cfg = FeishuConfig(app_id="test", app_secret="test")
        auth = FeishuAuthService(cfg)
        client = FeishuAppBotClient(cfg, auth)
        check(hasattr(client, "send_interactive_card"), "send_interactive_card method exists")
        check(hasattr(client, "send_text"), "send_text method exists")
        check(hasattr(client, "send_post"), "send_post method exists")
        check(hasattr(client, "reply_text"), "reply_text method exists")
    except Exception as e:
        check(False, f"Error: {e}")


def test_06_lark_sdk_available():
    heading("lark-oapi SDK Availability")
    try:
        import lark_oapi as lark
        check(True, "lark-oapi imported successfully")

        from lark_oapi.api.docx.v1 import CreateDocumentRequest
        from lark_oapi.api.bitable.v1 import CreateAppRequest
        from lark_oapi.api.sheets.v3 import CreateSpreadsheetRequest
        from lark_oapi.api.contact.v3 import GetUserRequest
        from lark_oapi.api.calendar.v4 import CreateCalendarEventRequest
        from lark_oapi.api.task.v2 import CreateTaskRequest

        check(True, "docx CreateDocumentRequest")
        check(True, "bitable CreateAppRequest")
        check(True, "sheets CreateSpreadsheetRequest")
        check(True, "contact GetUserRequest")
        check(True, "calendar CreateCalendarEventRequest")
        check(True, "task CreateTaskRequest")

        # Card action trigger via dispatcher (not direct import)
        builder = lark.EventDispatcherHandler.builder("", "")
        check(
            hasattr(builder, "register_p2_card_action_trigger"),
            "card action trigger method exists",
        )
    except ImportError as e:
        check(False, f"lark-oapi import failed: {e}")


def test_07_errors_hierarchy():
    heading("Exception Class Hierarchy")
    try:
        from omka.app.integrations.feishu.errors import (
            FeishuApiError,
            FeishuAuthError,
            FeishuConfigError,
            FeishuError,
            FeishuEventError,
            FeishuSendError,
        )

        check(issubclass(FeishuApiError, FeishuError), "FeishuApiError < FeishuError")
        check(issubclass(FeishuAuthError, FeishuError), "FeishuAuthError < FeishuError")
        check(issubclass(FeishuConfigError, FeishuError), "FeishuConfigError < FeishuError")
        check(issubclass(FeishuEventError, FeishuError), "FeishuEventError < FeishuError")
        check(issubclass(FeishuSendError, FeishuError), "FeishuSendError < FeishuError")

        err = FeishuApiError("test error", "99999")
        check(str(err) == "test error", "Exception message correct")
        check(err.error_code == "99999", "Exception code correct")
    except Exception as e:
        check(False, f"Error: {e}")


def test_08_command_router_handlers():
    heading("Command Router Handler Registration")
    try:
        from omka.app.integrations.feishu.config import FeishuConfig
        from omka.app.integrations.feishu.command_router import FeishuCommandRouter

        cfg = FeishuConfig(app_id="test", app_secret="test")
        router = FeishuCommandRouter(cfg)

        new_handlers = ["doc", "base", "sheet", "calendar", "task"]
        for h in new_handlers:
            handler = router._get_handler(h)
            check(handler is not None, f"Handler registered: {h}")
    except Exception as e:
        check(False, f"Error: {e}")


def test_09_help_text():
    heading("Help Text Completeness")
    try:
        from omka.app.integrations.feishu.command_router import HELP_TEXT

        check("/omka doc digest" in HELP_TEXT, "Help has doc digest")
        check("/omka doc create" in HELP_TEXT, "Help has doc create")
        check("/omka base import" in HELP_TEXT, "Help has base import")
        check("/omka base create" in HELP_TEXT, "Help has base create")
        check("/omka sheet export" in HELP_TEXT, "Help has sheet export")
        check("/omka calendar list" in HELP_TEXT, "Help has calendar list")
        check("/omka calendar review" in HELP_TEXT, "Help has calendar review")
        check("/omka task add" in HELP_TEXT, "Help has task add")
    except Exception as e:
        check(False, f"Error: {e}")


def test_09b_rich_formatting():
    heading("Rich Markdown Parsing")
    try:
        from omka.app.integrations.feishu.api_service import _build_content_json, _parse_inline

        digest = (
            "# OMKA Daily\n\n"
            "> 共 10 条\n\n"
            "---\n\n"
            "## 1. **Important** Item\n\n"
            "- **Link**: [GitHub](https://github.com)\n"
            "- **Score**: 0.95\n\n"
            "---\n\n"
            "## Tasks\n\n"
            "- [ ] [Read this](https://example.com)\n"
        )
        blocks = _build_content_json(digest)

        check(len(blocks) >= 9, f"Block count >= 9 (got {len(blocks)})")

        types_seen = set(b["block_type"] for b in blocks)
        check(3 in types_seen, "heading1 block present")
        check(4 in types_seen, "heading2 block present")
        check(15 in types_seen, "quote block present")
        check(22 in types_seen, "divider block present")
        check(12 in types_seen, "bullet block present")
        check(17 in types_seen, "todo block present")

        inline = _parse_inline("hello **bold** [link](https://x.com) world")
        check(len(inline) >= 4, f"Inline elements >= 4 (got {len(inline)})")
        has_bold = any(
            e.get("text_run", {}).get("text_element_style", {}).get("bold")
            for e in inline
        )
        has_link = any(
            e.get("text_run", {}).get("text_element_style", {}).get("link")
            for e in inline
        )
        check(has_bold, "bold inline parsed")
        check(has_link, "link inline parsed")
    except Exception as e:
        check(False, f"Error: {e}")


def test_10_env_config():
    heading("Environment Variable Configuration Check")
    env_file = PROJECT_ROOT / ".env.example"
    check(env_file.exists(), ".env.example exists")

    content = env_file.read_text(encoding="utf-8")
    check("FEISHU_DOC_FOLDER_TOKEN" in content, ".env.example has DOC_FOLDER_TOKEN")
    check("FEISHU_BASE_FOLDER_TOKEN" in content, ".env.example has BASE_FOLDER_TOKEN")
    check("FEISHU_SHEET_FOLDER_TOKEN" in content, ".env.example has SHEET_FOLDER_TOKEN")
    check("FEISHU_DEFAULT_CALENDAR_ID" in content, ".env.example has DEFAULT_CALENDAR_ID")


def main():
    print("=" * 60)
    print("  OMKA Feishu Built-in Capabilities Integration Test")
    print("=" * 60)

    test_01_imports()
    test_02_command_types()
    test_03_config_fields()
    test_04_api_service_init()
    test_05_client_card_support()
    test_06_lark_sdk_available()
    test_07_errors_hierarchy()
    test_08_command_router_handlers()
    test_09_help_text()
    test_09b_rich_formatting()
    test_10_env_config()

    print(f"\n{'=' * 60}")
    total = passed + failed
    print(f"  Result: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
