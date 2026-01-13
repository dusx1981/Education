from __future__ import annotations

import os
import re
import json
import logging
from typing import AsyncGenerator, Optional
from typing_extensions import override
import aiohttp

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from utils import print_exception_stack

logger = logging.getLogger(__name__)


class QwenLlm(BaseLlm):
    """千问模型适配器 - 完全遵循ADK框架规范"""
    
    def __init__(
        self, 
        model_name: str = "qwen2.5-7b-instruct",
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/api/v1",
        **kwargs
    ):
        # 调用父类初始化
        super().__init__(model=model_name, **kwargs)
        
        # 存储配置
        self._model_name = model_name
        self._api_key = api_key or self._get_api_key()
        self._base_url = base_url
        
        # 初始化会话
        self._session = None
        self._default_temperature = kwargs.get("temperature", 0.7)
        self._default_max_tokens = kwargs.get("max_tokens", 2048)
    
    def _get_api_key(self) -> str:
        """从环境变量获取 API Key"""
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "千问 API Key 未提供。请设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY"
            )
        return api_key
    
    async def _ensure_session(self):
        """确保 aiohttp session 存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
    
    def _convert_to_qwen_messages(self, request: LlmRequest) -> list[dict]:
        """将 LlmRequest 转换为千问 API 的消息格式"""
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
    
    def _convert_to_qwen_parameters(self, request: LlmRequest) -> dict:
        """转换生成参数"""
        config = request.config
        
        params = {
            "temperature": getattr(config, "temperature", 0.7),
            "max_tokens": getattr(config, "max_output_tokens", 2048),
        }
        
        # 可选参数
        if config and hasattr(config, "top_p") and config.top_p is not None:
            params["top_p"] = config.top_p
        
        if config and hasattr(config, "top_k") and config.top_k is not None:
            params["top_k"] = config.top_k
        
        if config and hasattr(config, "repetition_penalty") and config.repetition_penalty is not None:
            params["repetition_penalty"] = config.repetition_penalty
        
        return params
    
    @override
    async def generate_content_async(
        self, 
        llm_request: LlmRequest, 
        stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """发送请求到千问模型"""
        await self._ensure_session()
        
        # 构建请求体
        payload = {
            "model": self.model,
            "input": {
                "messages": self._convert_to_qwen_messages(llm_request)
            },
            "parameters": {
                **self._convert_to_qwen_parameters(llm_request),
                "stream": stream
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(
            '发送千问API请求, 模型: %s, 流式: %s',
            self.model,
            stream
        )
        
        try:
            if not stream:
                # 非流式调用
                async with self._session.post(
                    f"{self._base_url}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    llm_response = self._parse_qwen_response(data)
                    logger.debug('接收到千问非流式响应')
                    yield llm_response
                    
            else:
                # 流式调用 - 核心修复点
                async with self._session.post(
                    f"{self._base_url}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    response.raise_for_status()
                    
                    # 获取Content-Type判断响应格式
                    content_type = response.headers.get('Content-Type', '')
                    logger.debug(f"响应Content-Type: {content_type}")
                    
                    # 处理流式响应
                    if 'text/event-stream' in content_type:
                        # 情况1：SSE流式响应
                        async for response_item in self._process_sse_stream(response):
                            yield response_item
                    else:
                        # 情况2：JSON流式响应
                        async for response_item in self._process_json_stream(response):
                            yield response_item
                            
        except Exception as e:
            logger.error(f"千问API调用出错: {e}")
            raise
        finally:
            await self.close()

    def _clean_markdown_json(self, text: str) -> str:
        """清理 Markdown 代码块，专注于提取 JSON 字符串"""
        if not text or not isinstance(text, str):
            return ""
        
        text = text.strip()
        
        # 正则表达式：匹配代码块开始标记
        code_block_start = re.compile(r'^\s*```(?:json)?\s*$')
        code_block_end = re.compile(r'^\s*```\s*$')
        
        lines = text.split('\n')
        cleaned_lines = []
        in_code_block = False
        
        for line in lines:
            # 检查是否是代码块开始
            if code_block_start.match(line):
                in_code_block = True
                continue
            # 检查是否是代码块结束
            elif in_code_block and code_block_end.match(line):
                in_code_block = False
                continue
            # 如果不在代码块中，保留该行
            elif not in_code_block:
                cleaned_lines.append(line)
            # 在代码块中，保留内容行
            else:
                cleaned_lines.append(line)
        
        # 重新组合文本
        result = '\n'.join(cleaned_lines)
        
        # 如果结果为空，尝试直接提取代码块内容
        if not result.strip():
            # 使用正则表达式提取代码块内容
            extract_pattern = r'```(?:json)?\s*([\s\S]*?)```'
            matches = re.findall(extract_pattern, text, re.IGNORECASE)
            if matches:
                # 返回第一个匹配的内容
                return matches[0].strip()
        
        return result.strip()
    
    def _extract_json_string(self, text: str) -> str:
        """从文本中提取 JSON 字符串（支持对象和数组）"""
        # 移除文本两端的空白字符
        text = text.strip()
        
        # 模式1：尝试提取完整的 JSON（对象或数组）
        json_pattern = r'(?s)(\{.*\}|\[.*\])'
        
        # 模式2：更精确的匹配，支持嵌套
        # 这个模式会匹配从第一个 '{' 或 '[' 开始到最后一个匹配的 '}' 或 ']' 的内容
        json_pattern_advanced = r'(?s)((?:\[(?:[^\[\]]|(?1))*\]|\{(?:[^{}]|(?1))*\}))'
        
        # 模式3：简单但有效的提取，匹配最外层的大括号或中括号
        json_pattern_simple = r'(?s)([\[\{](?:[^\[\]\{\}]|(?R))*[\]\}])'
        
        try:
            # 首先尝试匹配最外层的 JSON 结构
            import regex
            match = regex.search(json_pattern_simple, text)
            if match:
                json_str = match.group(0)
                # 验证是否为有效的 JSON
                try:
                    json.loads(json_str)
                    return json_str
                except json.JSONDecodeError:
                    pass
            
            # 如果 regex 不可用，使用标准 re 的简化方法
            # 查找第一个可能的开始标记
            start_chars = {'{': '}', '[': ']'}
            for start_char, end_char in start_chars.items():
                start_idx = text.find(start_char)
                if start_idx != -1:
                    # 使用栈匹配找到对应的结束标记
                    stack = []
                    for i in range(start_idx, len(text)):
                        char = text[i]
                        if char == start_char:
                            stack.append(char)
                        elif char == end_char:
                            if stack and stack[-1] == start_char:
                                stack.pop()
                            if not stack:  # 栈为空，找到匹配的结束位置
                                json_str = text[start_idx:i+1]
                                # 验证 JSON 格式
                                try:
                                    json.loads(json_str)
                                    return json_str
                                except json.JSONDecodeError:
                                    continue  # 继续查找下一个可能的 JSON
            return text
        except Exception:
            # 如果所有方法都失败，返回原始文本
            return text
    
    async def _process_json_stream(self, response: aiohttp.ClientResponse) -> AsyncGenerator[LlmResponse, None]:
        """处理JSON格式的流式响应"""
        buffer = ""
        accumulated_text = ""
        
        async for chunk in response.content.iter_any():
            if not chunk:
                continue
            
            chunk_str = chunk.decode('utf-8', errors='ignore')
            buffer += chunk_str
            
            # 尝试解析完整的JSON对象
            try:
                # 寻找完整的JSON对象边界
                start = buffer.find('{')
                end = buffer.rfind('}')
                
                if start != -1 and end != -1 and end > start:
                    json_str = buffer[start:end+1]
                    # 移除已处理的部分
                    buffer = buffer[end+1:]
                    
                    data = json.loads(json_str)
                    
                    # 提取文本和完成原因
                    current_text = ""
                    finish_reason_str = None
                    usage_data = None
                    
                    if "output" in data:
                        output = data.get("output", {})
                        current_text = output.get("text", "")
                        finish_reason_str = output.get("finish_reason")
                    elif "choices" in data:
                        choices = data.get("choices", [])
                        if choices:
                            choice = choices[0]
                            if "message" in choice:
                                current_text = choice["message"].get("content", "")
                                finish_reason_str = choice.get("finish_reason")
                            elif "delta" in choice:
                                current_text = choice["delta"].get("content", "")
                                finish_reason_str = choice.get("finish_reason")
                    
                    # 处理使用情况
                    if "usage" in data:
                        usage_data = data["usage"]
                    
                    # 计算增量文本
                    if current_text and current_text.startswith(accumulated_text):
                        incremental_text = current_text[len(accumulated_text):]
                        accumulated_text = current_text
                        
                        if incremental_text:
                            cleaned_text = self._clean_markdown_json(incremental_text)
                            # 返回增量部分
                            yield LlmResponse(
                                content=types.Content(
                                    parts=[types.Part(text=cleaned_text)],
                                    role="assistant"
                                ),
                                finish_reason=None,  # 中间chunk没有完成原因
                                # model_version=self._model_name
                            )
                    
                    # 如果有完成原因，发送最终响应
                    if finish_reason_str:
                        # 映射完成原因
                        finish_reason = self._map_finish_reason(finish_reason_str)
                        
                        # 创建使用情况元数据
                        usage_metadata = None
                        if usage_data:
                            usage_metadata = types.GenerateContentResponseUsageMetadata(
                                prompt_token_count=usage_data.get("input_tokens", 0),
                                total_token_count=usage_data.get("total_tokens", 0)
                            )
                        
                        yield LlmResponse(
                            content=None,  # 最终响应通常没有内容
                            finish_reason=finish_reason,
                            usage_metadata=usage_metadata,
                            # model_version=self._model_name
                        )
                        
            except json.JSONDecodeError:
                # JSON不完整，等待更多数据
                continue
            except Exception as e:
                print_exception_stack(e, "解析JSON出错")
                logger.warning(f"解析JSON出错: {e}")
                continue
    
    async def _process_sse_stream(self, response: aiohttp.ClientResponse) -> AsyncGenerator[LlmResponse, None]:
        """处理SSE格式的流式响应"""
        buffer = ""
        accumulated_text = ""
        
        async for chunk in response.content.iter_any():
            if not chunk:
                continue
            
            chunk_str = chunk.decode('utf-8', errors='ignore')
            buffer += chunk_str
            
            # 处理SSE格式：data: {json}\n\n
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                if not line:
                    continue
                
                if line.startswith('data: '):
                    data_str = line[6:]  # 移除 "data: " 前缀
                    
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        
                        # 提取文本和完成原因
                        current_text = ""
                        finish_reason_str = None
                        
                        if "output" in data:
                            output = data.get("output", {})
                            current_text = output.get("text", "")
                            finish_reason_str = output.get("finish_reason")
                        elif "choices" in data:
                            choices = data.get("choices", [])
                            if choices:
                                choice = choices[0]
                                if "message" in choice:
                                    current_text = choice["message"].get("content", "")
                                    finish_reason_str = choice.get("finish_reason")
                                elif "delta" in choice:
                                    current_text = choice["delta"].get("content", "")
                                    finish_reason_str = choice.get("finish_reason")
                        
                        # 计算增量文本
                        if current_text and current_text.startswith(accumulated_text):
                            incremental_text = current_text[len(accumulated_text):]
                            accumulated_text = current_text
                            
                            if incremental_text:
                                # 返回增量部分
                                yield LlmResponse(
                                    content=types.Content(
                                        parts=[types.Part(text=incremental_text)],
                                        role="assistant"
                                    ),
                                    finish_reason=None,  # 中间chunk没有完成原因
                                    # model_version=self._model_name
                                )
                        
                        # 如果有完成原因，发送最终响应
                        if finish_reason_str:
                            finish_reason = self._map_finish_reason(finish_reason_str)
                            yield LlmResponse(
                                content=None,
                                finish_reason=finish_reason,
                                # model_version=self._model_name
                            )
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON解析错误: {e}, data_str: {data_str}")
                        continue
    
    def _parse_qwen_response(self, response_data: dict) -> LlmResponse:
        """解析千问API响应（非流式）"""
        try:
            # 提取生成的文本
            text = ""
            if "output" in response_data:
                output = response_data.get("output", {})
                text = output.get("text", "")
            elif "choices" in response_data:
                choices = response_data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
            
            # 处理使用情况统计
            usage = response_data.get("usage", {})
            
            # 处理完成原因
            finish_reason_str = response_data.get("finish_reason", "stop")
            finish_reason = self._map_finish_reason(finish_reason_str)
            
            return LlmResponse(
                content=types.Content(
                    parts=[types.Part(text=text)],
                    role="assistant"
                ),
                finish_reason=finish_reason,
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=usage.get("input_tokens", 0),
                    total_token_count=usage.get("total_tokens", 0)
                ),
                # model_version=self._model_name
            )
        except Exception as e:
            logger.error('解析千问响应失败: %s, 响应数据: %s', e, response_data)
            # 如果解析失败，返回没有使用情况信息的响应
            return LlmResponse(
                content=types.Content(
                    parts=[types.Part(text=text)],
                    role="assistant"
                ),
                finish_reason=self._map_finish_reason(response_data.get("finish_reason", "stop")),
                # model_version=self._model_name
            )
    
    def _map_finish_reason(self, qwen_finish_reason: str) -> Optional[types.FinishReason]:
        """将千问的完成原因映射到 ADK 的 FinishReason"""
        if not qwen_finish_reason:
            return None
        
        mapping = {
            "stop": types.FinishReason.STOP,
            "length": types.FinishReason.MAX_TOKENS,
            "content_filter": types.FinishReason.SAFETY,
            "function_call": types.FinishReason.STOP,
            "tool_calls": types.FinishReason.STOP,
        }
        
        return mapping.get(qwen_finish_reason.lower(), types.FinishReason.STOP)
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    @classmethod
    @override
    def supported_models(cls) -> list[str]:
        """提供支持的模型列表"""
        return [
            r'qwen2\.5-.*',
            r'qwen2\.?5-.*-instruct',
        ]


def create_qwen_llm(
    model_size: str = "72b",
    api_key: Optional[str] = None,
    **kwargs
) -> QwenLlm:
    """创建千问模型实例的工厂函数"""
    model_name = f"qwen2.5-{model_size}-instruct"
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    
    if not api_key:
        raise ValueError(
            "请提供千问 API Key，或设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY"
        )
    
    return QwenLlm(
        model_name=model_name,
        api_key=api_key,
        **kwargs
    )