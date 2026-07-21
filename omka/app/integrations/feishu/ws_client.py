import asyncio
import multiprocessing
import os
import threading

from omka.app.core.logging import logger
from omka.app.integrations.feishu.config import FeishuConfig


def _run_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _ws_process_main(config_dict: dict) -> None:
    import concurrent.futures
    import json
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
    from lark_oapi.ws import Client as WsClient

    from omka.app.integrations.feishu.config import FeishuConfig
    from omka.app.integrations.feishu.event_handler import FeishuEventHandler

    logger.info("飞书长连接子进程启动 | pid=%s", os.getpid())

    config = FeishuConfig(**config_dict)
    event_handler_instance = FeishuEventHandler(config)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=_run_event_loop, args=(loop,), daemon=True)
    loop_thread.start()
    logger.info("事件循环线程已启动")

    def handle_message(data: P2ImMessageReceiveV1) -> None:
        logger.info("收到飞书长连接消息事件")
        import traceback
        try:
            event = data.event
            if not event:
                logger.warning("事件数据为空")
                return

            message = event.message
            sender = event.sender

            chat_id = message.chat_id if message else ""
            chat_type = message.chat_type if message else ""
            message_id = message.message_id if message else ""
            message_type = message.message_type if message else ""
            content = message.content if message else ""
            open_id = sender.sender_id.open_id if sender and sender.sender_id else ""

            logger.info(
                "解析消息 | message_id=%s | chat_type=%s | sender=%s | type=%s | content=%s",
                message_id, chat_type, open_id, message_type, content[:50] if content else ""
            )

            event_id = data.header.event_id if data.header else ""
            # lark-oapi SDK 已在连接层完成事件验证，WS 事件的 header 中不含 token
            # 因此回退到 config.verification_token，使 _validate_token() 通过
            token = data.header.token if data.header and data.header.token else config.verification_token

            payload = {
                "header": {
                    "event_id": event_id,
                    "event_type": "im.message.receive_v1",
                    "token": token,
                },
                "event": {
                    "message": {
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "message_id": message_id,
                        "message_type": message_type,
                        "content": content,
                    },
                    "sender": {
                        "sender_id": {
                            "open_id": open_id,
                        }
                    }
                },
            }


            logger.info("提交事件到处理器")
            future = asyncio.run_coroutine_threadsafe(
                event_handler_instance.handle_event(payload), loop
            )
            try:
                result = future.result(timeout=120)
                logger.info("事件处理完成 | result=%s", result)
            except concurrent.futures.TimeoutError:
                logger.error("事件处理超时（120秒）")
            except Exception as e:
                logger.error("事件处理异常 | error=%s | type=%s\n%s", e, type(e).__name__, traceback.format_exc())

        except Exception as e:
            logger.error("处理长连接消息事件失败 | error=%s | type=%s\n%s", e, type(e).__name__, traceback.format_exc())

    def handle_card_action(data) -> None:
        logger.info("收到飞书卡片动作事件")
        import traceback
        try:
            event = getattr(data, "event", None)
            if not event:
                return

            action = getattr(event, "action", None)
            action_value_str = action.value if action and hasattr(action, "value") else "{}"
            try:
                action_value = json.loads(action_value_str)
            except (json.JSONDecodeError, TypeError):
                action_value = {"raw": action_value_str}

            logger.info(
                "卡片动作解析 | action_type=%s | candidate_id=%s",
                action_value.get("action", "?"),
                action_value.get("id", "?"),
            )

            act = action_value.get("action", "")
            candidate_id = action_value.get("id", "")
            if act and candidate_id:
                operator = getattr(event, "operator", None)
                open_id = operator.open_id if operator and hasattr(operator, "open_id") else ""

                synthetic_text = json.dumps({"text": f"/omka candidate {act} {candidate_id}"})
                synthetic_payload = {
                    "header": {
                        "event_id": data.header.event_id if data.header else "",
                        "event_type": "im.message.receive_v1",
                        "token": config.verification_token,
                    },
                    "event": {
                        "message": {
                            "chat_id": "",
                            "chat_type": "p2p",
                            "message_id": "",
                            "message_type": "text",
                            "content": synthetic_text,
                        },
                        "sender": {
                            "sender_id": {"open_id": open_id},
                        },
                    },
                }
                logger.info("卡片动作转为命令 | cmd=%s %s", act, candidate_id)
                future = asyncio.run_coroutine_threadsafe(
                    event_handler_instance.handle_event(synthetic_payload), loop
                )
                try:
                    future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    logger.error("卡片动作处理超时")
        except Exception as e:
            logger.error("处理卡片动作失败 | error=%s\n%s", e, traceback.format_exc())

    dispatcher = lark.EventDispatcherHandler.builder(
        config.encrypt_key,
        config.verification_token,
    ).register_p2_im_message_receive_v1(handle_message) \
     .register_p2_card_action_trigger(handle_card_action) \
     .build()

    ws_client = WsClient(
        app_id=config.app_id,
        app_secret=config.app_secret,
        event_handler=dispatcher,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )

    logger.info("飞书长连接开始 | app_id=%s", config.app_id[:8] + "****")
    ws_client.start()


class FeishuWebSocketClient:
    def __init__(self, config: FeishuConfig) -> None:
        self._config = config
        self._running = False
        self._process: multiprocessing.Process | None = None

    def start(self) -> None:
        if self._running:
            logger.warning("飞书长连接客户端已在运行")
            return
        if not self._config.enabled:
            logger.info("飞书未启用，跳过长连接")
            return
        if not self._config.is_configured():
            logger.warning("飞书凭证未配置，跳过长连接")
            return
        self._running = True
        config_dict = self._config.model_dump()
        self._process = multiprocessing.Process(
            target=_ws_process_main,
            args=(config_dict,),
            daemon=True,
            name="feishu-ws"
        )
        self._process.start()
        logger.info("飞书长连接客户端已启动 | pid=%s", self._process.pid)

    def stop(self) -> None:
        self._running = False
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)
        logger.info("飞书长连接客户端已停止")

    @property
    def is_running(self) -> bool:
        return self._running and self._process is not None and self._process.is_alive()


_ws_client: FeishuWebSocketClient | None = None


def get_ws_client() -> FeishuWebSocketClient | None:
    return _ws_client


def init_ws_client(config: FeishuConfig) -> FeishuWebSocketClient:
    """初始化全局长连接客户端"""
    global _ws_client
    _ws_client = FeishuWebSocketClient(config)
    return _ws_client
