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
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
    from lark_oapi.ws import Client as WsClient

    from omka.app.core.logging import setup_logging, logger as proc_logger
    from omka.app.integrations.feishu.config import FeishuConfig
    from omka.app.integrations.feishu.event_handler import FeishuEventHandler

    setup_logging()
    proc_logger.info("飞书长连接子进程启动 | pid=%s", os.getpid())

    config = FeishuConfig(**config_dict)
    event_handler_instance = FeishuEventHandler(config)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=_run_event_loop, args=(loop,), daemon=True)
    loop_thread.start()
    proc_logger.info("事件循环线程已启动")

    def handle_message(data: P2ImMessageReceiveV1) -> None:
        proc_logger.info("收到飞书长连接消息事件")
        import traceback
        try:
            event = data.event
            if not event:
                proc_logger.warning("事件数据为空")
                return

            message = event.message
            sender = event.sender

            chat_id = message.chat_id if message else ""
            chat_type = message.chat_type if message else ""
            message_id = message.message_id if message else ""
            message_type = message.message_type if message else ""
            content = message.content if message else ""
            open_id = sender.sender_id.open_id if sender and sender.sender_id else ""

            proc_logger.info(
                "解析消息 | message_id=%s | chat_type=%s | sender=%s | type=%s | content=%s",
                message_id, chat_type, open_id, message_type, content[:50] if content else ""
            )

            event_id = data.header.event_id if data.header else ""
            token = data.header.token if data.header else config.verification_token

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

            import concurrent.futures
            proc_logger.info("提交事件到处理器")
            future = asyncio.run_coroutine_threadsafe(
                event_handler_instance.handle_event(payload), loop
            )
            try:
                result = future.result(timeout=120)
                proc_logger.info("事件处理完成 | result=%s", result)
            except concurrent.futures.TimeoutError:
                proc_logger.error("事件处理超时（120秒）")
            except Exception as e:
                proc_logger.error("事件处理异常 | error=%s | type=%s\n%s", e, type(e).__name__, traceback.format_exc())

        except Exception as e:
            proc_logger.error("处理长连接消息事件失败 | error=%s | type=%s\n%s", e, type(e).__name__, traceback.format_exc())

    dispatcher = lark.EventDispatcherHandler.builder(
        config.encrypt_key,
        config.verification_token,
    ).register_p2_im_message_receive_v1(handle_message).build()

    ws_client = WsClient(
        app_id=config.app_id,
        app_secret=config.app_secret,
        event_handler=dispatcher,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )

    proc_logger.info("飞书长连接开始 | app_id=%s", config.app_id[:8] + "****")
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
