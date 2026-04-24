"""
SAP OpenSQL API Client
通过 HTTP POST 发送 OpenSQL 查询到 SAP ECC，返回解析后的 JSON 结果
"""
import requests
import base64
import json
import time
from typing import Dict, List, Any, Optional
from loguru import logger

from .exceptions import (
    SAPConnectionError,
    SAPAuthenticationError,
    SAPDataError,
    SAPTimeoutError,
)


class SAPOpenSQLClient:
    """SAP OpenSQL API 客户端"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化客户端

        Args:
            config: opensql 配置段，结构示例:
                {
                    "endpoint": "https://host/abb/ybc_query_mind//SAPQueryMind",
                    "sap_client": "800",
                    "auth": {"type": "basic_token", "token": "Q05..."},
                    "request": {"timeout": 120, "max_retries": 3, "retry_delay": 5}
                }

        auth 支持两种方式:
          1. basic_token: 直接提供已编码的 Base64 令牌
             {"type": "basic_token", "token": "Q05QRVdBTjY6VEVNUEB..."}
          2. basic: 提供用户名密码，由代码编码
             {"type": "basic", "username": "xxx", "password": "xxx"}
        """
        self.endpoint = config["endpoint"]
        self.sap_client = config["sap_client"]

        auth_cfg = config["auth"]
        self.auth_type = auth_cfg["type"]
        raw_token = auth_cfg.get("token", "").strip()
        # 用户可能输入 "Basic xxxxx"，自动去掉前缀
        if raw_token.lower().startswith("basic "):
            raw_token = raw_token[6:].strip()
        self.auth_token = raw_token
        self.username = auth_cfg.get("username", "")
        self.password = auth_cfg.get("password", "")

        req_cfg = config.get("request", {})
        self.timeout = req_cfg.get("timeout", 120)
        self.max_retries = req_cfg.get("max_retries", 3)
        self.retry_delay = req_cfg.get("retry_delay", 5)
        self.verify_ssl = req_cfg.get("verify_ssl", False)

        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        if not self.verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._setup_auth()

    # ------------------------------------------------------------------
    def _setup_auth(self):
        """配置认证 headers"""
        if self.auth_type == "basic_token":
            # 直接使用已编码的 Base64 令牌
            self.session.headers.update({"Authorization": f"Basic {self.auth_token}"})
        elif self.auth_type == "basic":
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            self.session.headers.update({"Authorization": f"Basic {encoded}"})
        else:
            raise SAPAuthenticationError(f"不支持的认证方式: {self.auth_type}")

        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    def execute(self, opensql: str) -> List[Dict[str, Any]]:
        """
        执行一条 OpenSQL 语句，返回结果行列表

        Args:
            opensql: 完整的 ABAP OpenSQL 语句（以 . 结尾）

        Returns:
            解析后的 JSON 行列表，例如 [{"FIELD1": "val", ...}, ...]

        Raises:
            SAPConnectionError, SAPAuthenticationError, SAPDataError, SAPTimeoutError
        """
        url = f"{self.endpoint}?sap-client={self.sap_client}"

        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"[Attempt {attempt}] POST {url}")
                logger.debug(f"  SQL: {opensql[:200]}{'...' if len(opensql) > 200 else ''}")

                payload = json.dumps({"ACTION": "", "SQL": opensql})
                resp = self.session.post(url, data=payload, timeout=self.timeout)

                if resp.status_code == 401:
                    raise SAPAuthenticationError("SAP 认证失败 (HTTP 401)")
                if resp.status_code == 403:
                    raise SAPAuthenticationError("SAP 权限不足 (HTTP 403)")
                if resp.status_code >= 500:
                    raise SAPConnectionError(f"SAP 服务端错误 (HTTP {resp.status_code})")
                # 检查非 JSON 错误响应（SAP 返回纯文本错误信息，如 SYNTAX_ERROR_...)
                text = resp.text.strip()
                if text and not text.startswith(('[', '{')):
                    raise SAPDataError(f"SAP 返回错误 (HTTP {resp.status_code}): {text[:300]}")
                if resp.status_code >= 400:
                    raise SAPDataError(
                        f"SAP 请求失败 (HTTP {resp.status_code}): {resp.text[:500]}"
                    )

                return self._parse_response(resp)

            except requests.exceptions.Timeout:
                last_err = SAPTimeoutError(f"请求超时 ({self.timeout}s)")
                logger.warning(f"  超时，第 {attempt}/{self.max_retries} 次")
            except requests.exceptions.ConnectionError as e:
                last_err = SAPConnectionError(f"连接失败: {e}")
                logger.warning(f"  连接失败，第 {attempt}/{self.max_retries} 次")
            except (SAPAuthenticationError, SAPDataError):
                raise  # 不重试
            except Exception as e:
                last_err = SAPDataError(f"未知错误: {e}")
                logger.warning(f"  异常: {e}")

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        raise last_err  # type: ignore[misc]

    # ------------------------------------------------------------------
    def _parse_response(self, resp: requests.Response) -> List[Dict[str, Any]]:
        """
        解析 SAP OpenSQL API 的 HTTP 响应

        响应格式可能为:
          1. 直接 JSON 数组: [{"F1":"v1"}, ...]
          2. JSON 对象含 body 字段: {"body": "[{...}]"}
          3. 纯文本 JSON 数组字符串
        """
        text = resp.text.strip()
        if not text:
            return []

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise SAPDataError(f"响应不是有效 JSON: {text[:300]}")

        # 情况 1: 直接数组
        if isinstance(data, list):
            return data

        # 情况 2: 对象含 body 字段
        if isinstance(data, dict):
            body = data.get("body", data.get("BODY", ""))
            if isinstance(body, str):
                try:
                    rows = json.loads(body)
                    if isinstance(rows, list):
                        return rows
                except json.JSONDecodeError:
                    pass
            # body 本身就是 list
            if isinstance(body, list):
                return body
            # 单行结果封装
            return [data]

        raise SAPDataError(f"无法解析响应格式: {text[:300]}")

    # ------------------------------------------------------------------
    def test_connection(self) -> bool:
        """测试连接是否正常（查询 ZPP_PRODLINE_MAT，避免使用无权限的标准表）"""
        try:
            sql = "SELECT PRODLINE INTO TABLE @DATA(lt_data) FROM ZPP_PRODLINE_MAT UP TO 1 ROWS."
            result = self.execute(sql)
            logger.info(f"✓ OpenSQL API 连接正常，测试返回 {len(result)} 行")
            return True
        except Exception as e:
            logger.error(f"✗ OpenSQL API 连接失败: {e}")
            raise
