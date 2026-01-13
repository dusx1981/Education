from __future__ import annotations

import os
import logging
from typing import AsyncGenerator, Optional
from typing_extensions import override

from openai import AsyncOpenAI
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from utils import print_exception_stack

logger = logging.getLogger(__name__)


class OpenAILlm(BaseLlm):
    """OpenAI 模型适配器 - 使用官方 AsyncOpenAI 客户端"""
    
    def __init__(
        self, 
        model_name: str = "qwen2.5-72b-instruct",
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        **kwargs
    ):
        # 调用父类初始化
        super().__init__(model=model_name, **kwargs)
        
        # 存储配置
        self._model_name = model_name
        self._api_key = api_key or self._get_api_key()
        self._base_url = base_url
        
        # 初始化 OpenAI 客户端
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=30.0,  # 30秒超时
        )
        
        # 存储默认参数
        self._default_temperature = kwargs.get("temperature", 0.7)
        self._default_max_tokens = kwargs.get("max_tokens", 2048)
    
    def _get_api_key(self) -> str:
        """从环境变量获取 API Key"""
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API Key 未提供。请设置环境变量 DASHSCOPE_API_KEY"
            )
        return api_key
    
    def _convert_to_openai_messages(self, request: LlmRequest) -> list[dict]:
        """将 LlmRequest 转换为 OpenAI API 的消息格式"""
        messages = []
        
        # 处理系统指令
        if request.config and hasattr(request.config, 'system_instruction') and request.config.system_instruction:
            messages.append({
                "role": "system",
                "content": request.config.system_instruction
            })
        
        # 处理对话历史
        for content in request.contents:
            # 确定角色：user 或 assistant
            role = "user" if content.role in ["user", "USER"] else "assistant"
            
            # 提取文本内容
            text_parts = []
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
            
            if text_parts:
                messages.append({
                    "role": role,
                    "content": "\n".join(text_parts)
                })
        
        return messages
    
    def _get_generation_parameters(self, request: LlmRequest) -> dict:
        """获取生成参数"""
        config = request.config
        
        params = {
            "model": self._model_name,
            "temperature": getattr(config, "temperature", self._default_temperature),
            "max_tokens": getattr(config, "max_output_tokens", self._default_max_tokens),
        }
        
        # 可选参数
        if config and hasattr(config, "top_p") and config.top_p is not None:
            params["top_p"] = config.top_p
        
        if config and hasattr(config, "frequency_penalty") and config.frequency_penalty is not None:
            params["frequency_penalty"] = config.frequency_penalty
        
        if config and hasattr(config, "presence_penalty") and config.presence_penalty is not None:
            params["presence_penalty"] = config.presence_penalty
        
        return params
    
    @override
    async def generate_content_async(
        self, 
        llm_request: LlmRequest, 
        stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """发送请求到 OpenAI 模型"""
        
        # 构建请求参数
        messages = self._convert_to_openai_messages(llm_request)
        params = self._get_generation_parameters(llm_request)
        
        logger.info(
            '发送OpenAI API请求, 模型: %s, 流式: %s, 消息数: %d',
            self._model_name,
            stream,
            len(messages)
        )
        
        try:
            if not stream:
                # 非流式调用
                response = await self._client.chat.completions.create(
                    messages=messages,
                    stream=False,
                    **params
                )
                
                llm_response = self._parse_openai_response(response)
                logger.debug('接收到OpenAI非流式响应')
                yield llm_response
                
            else:
                # 流式调用
                stream_response = await self._client.chat.completions.create(
                    messages=messages,
                    stream=True,
                    **params
                )
                
                async for chunk in stream_response:
                    yield self._parse_openai_chunk(chunk)
                        
                # 流结束后，发送完成响应
                yield LlmResponse(
                    content=None,
                    finish_reason=types.FinishReason.STOP,
                )
                        
        except Exception as e:
            logger.error(f"OpenAI API调用出错: {e}")
            # 重新抛出异常，让上层处理
            raise
    
    def _parse_openai_chunk(self, chunk) -> LlmResponse:
        """解析 OpenAI 流式响应块"""
        if not chunk.choices:
            return LlmResponse(
                content=None,
                finish_reason=None,
            )
        
        choice = chunk.choices[0]
        delta = choice.delta
        
        # 提取文本内容
        text_content = delta.content or ""
        
        # 如果有文本内容，返回文本响应
        if text_content:
            return LlmResponse(
                content=types.Content(
                    parts=[types.Part(text=text_content)],
                    role="assistant"
                ),
                finish_reason=None,  # 中间chunk没有完成原因
            )
        
        # 如果流结束，返回完成原因
        finish_reason = choice.finish_reason
        if finish_reason:
            return LlmResponse(
                content=None,
                finish_reason=self._map_finish_reason(finish_reason),
            )
        
        # 默认返回空响应
        return LlmResponse(
            content=None,
            finish_reason=None,
        )
    
    def _parse_openai_response(self, response) -> LlmResponse:
        """解析 OpenAI API 响应（非流式）"""
        try:
            # 提取生成的文本
            text = ""
            if response.choices and response.choices[0].message:
                text = response.choices[0].message.content or ""
            
            # 处理使用情况统计
            usage = response.usage
            
            # 处理完成原因
            finish_reason_str = response.choices[0].finish_reason if response.choices else "stop"
            finish_reason = self._map_finish_reason(finish_reason_str)
            
            return LlmResponse(
                content=types.Content(
                    parts=[types.Part(text=text)],
                    role="assistant"
                ),
                finish_reason=finish_reason,
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=usage.prompt_tokens if usage else 0,
                    total_token_count=usage.total_tokens if usage else 0
                ) if usage else None,
            )
        except Exception as e:
            logger.error('解析OpenAI响应失败: %s', e)
            # 如果解析失败，返回基本响应
            return LlmResponse(
                content=types.Content(
                    parts=[types.Part(text="")],
                    role="assistant"
                ),
                finish_reason=types.FinishReason.STOP,
            )
    
    def _map_finish_reason(self, openai_finish_reason: Optional[str]) -> Optional[types.FinishReason]:
        """将 OpenAI 的完成原因映射到 ADK 的 FinishReason"""
        if not openai_finish_reason:
            return None
        
        mapping = {
            "stop": types.FinishReason.STOP,
            "length": types.FinishReason.MAX_TOKENS,
            "content_filter": types.FinishReason.SAFETY,
            "function_call": types.FinishReason.STOP,
            "tool_calls": types.FinishReason.STOP,
        }
        
        return mapping.get(openai_finish_reason.lower(), types.FinishReason.STOP)
    
    async def close(self):
        """关闭 OpenAI 客户端"""
        if self._client:
            await self._client.close()
    
    @classmethod
    @override
    def supported_models(cls) -> list[str]:
        """提供支持的模型列表"""
        return [
            r'qwen2\.5-.*',
            r'qwen2\.?5-.*-instruct',
        ]


def create_openai_llm(
    model_name: str = "qwen2.5-72b-instruct",
    api_key: Optional[str] = None,
    **kwargs
) -> OpenAILlm:
    """创建 OpenAI 模型实例的工厂函数"""
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        raise ValueError(
            "请提供 OpenAI API Key，或设置环境变量 DASHSCOPE_API_KEY"
        )
    
    return OpenAILlm(
        model_name=model_name,
        api_key=api_key,
        **kwargs
    )


# # 兼容性：如果需要保留 QwenLlm 的名称但使用 OpenAI，可以这样包装
# class QwenLlm(OpenAILlm):
#     """兼容性类：保留 QwenLlm 名称但实际使用 OpenAI"""
    
#     def __init__(
#         self, 
#         model_name: str = "gpt-3.5-turbo",  # 默认使用 OpenAI 模型
#         api_key: Optional[str] = None,
#         base_url: Optional[str] = None,
#         **kwargs
#     ):
#         # 如果提供了 qwen 风格的模型名称，转换为 OpenAI 模型名称
#         if model_name.startswith("qwen"):
#             # 将 qwen 模型名称映射到 OpenAI 模型
#             model_mapping = {
#                 "qwen2.5-7b-instruct": "gpt-3.5-turbo",
#                 "qwen2.5-14b-instruct": "gpt-3.5-turbo-16k",
#                 "qwen2.5-72b-instruct": "gpt-4",
#             }
#             model_name = model_mapping.get(model_name, "gpt-3.5-turbo")
#             logger.info(f"将 Qwen 模型名称 {model_name} 映射到 OpenAI 模型 {model_name}")
        
#         # 如果未提供 api_key，尝试从 Qwen 环境变量获取
#         if not api_key:
#             qwen_api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
#             if qwen_api_key:
#                 logger.info("检测到 Qwen API Key，但将使用 OpenAI 服务")
#                 # 这里可以选择使用 Qwen Key 还是 OpenAI Key
#                 # 通常我们会要求用户设置 DASHSCOPE_API_KEY
#                 api_key = os.getenv("DASHSCOPE_API_KEY")
        
#         super().__init__(
#             model_name=model_name,
#             api_key=api_key,
#             base_url=base_url,
#             **kwargs
#         )
    
#     @classmethod
#     @override
#     def supported_models(cls) -> list[str]:
#         """提供支持的模型列表（兼容 Qwen 模型名称）"""
#         return [
#             r'qwen2\.5-.*',
#             r'qwen2\.?5-.*-instruct',
#             r'gpt-.*',  # 同时支持 OpenAI 模型
#         ]


# def create_qwen_llm(
#     model_size: str = "qwen2.5-72b-instruct",
#     api_key: Optional[str] = None,
#     **kwargs
# ) -> QwenLlm:
#     """创建 QwenLlm 实例的工厂函数（实际使用 OpenAI）"""
#     model_name = f"qwen2.5-{model_size}-instruct"
    
#     # 如果未提供 api_key，优先使用 OpenAI 的 key
#     if not api_key:
#         api_key = os.getenv("DASHSCOPE_API_KEY")
    
#     # 如果没有 OpenAI Key，尝试使用 Qwen Key（但会提示）
#     if not api_key:
#         api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
#         if api_key:
#             logger.warning("检测到 Qwen API Key，但本实现使用 OpenAI 服务，请设置 DASHSCOPE_API_KEY")
    
#     if not api_key:
#         raise ValueError(
#             "请提供 OpenAI API Key，或设置环境变量 DASHSCOPE_API_KEY"
#         )
    
#     return QwenLlm(
#         model_name=model_name,
#         api_key=api_key,
#         **kwargs
#     )