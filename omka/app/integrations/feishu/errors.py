class FeishuError(Exception):
    """飞书集成基础异常"""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class FeishuConfigError(FeishuError):
    """飞书配置错误"""


class FeishuAuthError(FeishuError):
    """飞书认证错误"""


class FeishuSendError(FeishuError):
    """飞书消息发送错误"""


class FeishuEventError(FeishuError):
    """飞书事件处理错误"""


class FeishuApiError(FeishuError):
    """飞书 API 调用错误"""


