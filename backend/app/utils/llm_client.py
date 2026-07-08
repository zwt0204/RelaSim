"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from ..config import Config
from .retry import retry_with_backoff
from .logger import get_logger

# 需要重试的异常：网络抖动、超时、限流、5xx 服务端错误（含中转站上游偶发 503）。
# 不重试鉴权/参数类 4xx（如 PermissionDeniedError、BadRequestError），因为重试也不会成功。
_RETRYABLE_LLM_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


logger = get_logger('mirofish.llm')


class LLMClient:
    """
    LLM客户端

    支持主/备双网关：主网关（LLM_*）在重试耗尽后仍失败时，
    自动切换到备用网关（LLM_FALLBACK_*）再试一次。
    备用网关通常更贵或更慢，仅作兜底，不参与常规调用。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        user_agent: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_base_url: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        # 部分中转网关的 WAF 会拦截 OpenAI SDK 默认的 "OpenAI/Python" User-Agent，
        # 返回 "Your request was blocked"。配置 LLM_USER_AGENT 可覆盖以绕过。
        user_agent = user_agent or Config.LLM_USER_AGENT
        default_headers = {"User-Agent": user_agent} if user_agent else None

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=default_headers
        )

        # 备用网关（可选）：主网关全部失败后才启用
        self.fallback_api_key = fallback_api_key or Config.LLM_FALLBACK_API_KEY
        self.fallback_base_url = fallback_base_url or Config.LLM_FALLBACK_BASE_URL
        self.fallback_model = fallback_model or Config.LLM_FALLBACK_MODEL_NAME

        self.fallback_client: Optional[OpenAI] = None
        if self.fallback_api_key and self.fallback_base_url:
            self.fallback_client = OpenAI(
                api_key=self.fallback_api_key,
                base_url=self.fallback_base_url,
                default_headers=default_headers,
            )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求。

        流程：
        1. 主网关调用，对可重试的网络/服务端错误自动指数退避重试；
        2. 主网关重试耗尽仍失败时，若配置了备用网关，则切到备用网关再试一次
           （备用网关也带自身的重试）。

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）

        Returns:
            模型响应文本
        """
        try:
            return self._chat_via(
                self.client, self.model, messages,
                temperature, max_tokens, response_format,
            )
        except Exception as primary_error:
            if self.fallback_client is None:
                raise
            logger.warning(
                f"主网关调用失败（{primary_error}），切换到备用网关 "
                f"{self.fallback_base_url} / {self.fallback_model} 重试..."
            )
            return self._chat_via(
                self.fallback_client, self.fallback_model, messages,
                temperature, max_tokens, response_format,
            )

    def _chat_via(
        self,
        client: OpenAI,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict],
    ) -> str:
        """在指定网关上发起调用（含指数退避重试）"""

        @retry_with_backoff(
            max_retries=3,
            initial_delay=2.0,
            exceptions=_RETRYABLE_LLM_ERRORS,
        )
        def _call() -> str:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if response_format:
                kwargs["response_format"] = response_format

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
            content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
            return content

        return _call()
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 8192,
        max_parse_retries: int = 2
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON

        对"输出被截断/格式不合法"的情况有自愈能力：解析失败时会自动重新生成，
        因为部分"思考型"模型（如 gemini-2.5-pro）会消耗大量 reasoning token，
        叙事又长，容易在 JSON 字符串中途被截断。

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数（默认调高到 8192，给长叙事 + reasoning 留足空间）
            max_parse_retries: 解析失败时重新生成的最大次数

        Returns:
            解析后的JSON对象
        """
        last_error: Optional[Exception] = None
        for attempt in range(max_parse_retries + 1):
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            # 清理markdown代码块标记
            cleaned_response = response.strip()
            cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < max_parse_retries:
                    logger.warning(
                        f"LLM 返回的 JSON 无法解析（可能被截断），"
                        f"第 {attempt + 1} 次重新生成... 错误: {e}"
                    )
                    continue
                raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}") from last_error

