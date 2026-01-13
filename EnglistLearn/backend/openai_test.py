import os
import sys
import asyncio
from google.adk.models.llm_request import LlmRequest
from google.genai import types
sys.path.insert(0, os.getcwd())
from openai_client import create_openai_llm
from qianwen import create_qwen_llm

async def test_openai_llm():
    """测试 OpenAI LLM 适配器"""
    # 创建模型实例
    llm = create_qwen_llm(
        temperature=0.7,
        max_tokens=100
    )
    
    # 创建请求
    request = LlmRequest(
        contents=[
            types.Content(
                parts=[types.Part(text="Hello, how are you?")],
                role="user"
            )
        ]
    )
    
    try:
        # 测试非流式
        # print("测试非流式响应...")
        # async for response in llm.generate_content_async(request, stream=False):
        #     if response.content and response.content.parts:
        #         print(f"Response: {response.content.parts[0].text}")
        
        # 测试流式
        print("\n测试流式响应...")
        full_response = ""
        async for response in llm.generate_content_async(request, stream=True):
            if response.content and response.content.parts:
                chunk = response.content.parts[0].text
                full_response += chunk
                print(chunk, end="", flush=True)
            elif response.finish_reason:
                print(f"\n完成原因: {response.finish_reason}")
        
        print(f"\n完整响应: {full_response}")
        
    finally:
        await llm.close()

if __name__ == "__main__":
    asyncio.run(test_openai_llm())