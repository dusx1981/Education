"""英语学习应用主程序"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import AsyncGenerator, Optional
import json
import uuid
import time
import logging

from google.adk.runners import InMemoryRunner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from google.adk.agents.run_config import RunConfig, StreamingMode

from utils import print_exception_stack
from agent import EnglishLearningAgent

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fun English Learning")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
# app.mount("/static", StaticFiles(directory="static"), name="static")

# 初始化Agent
english_agent = EnglishLearningAgent()
agent = english_agent.get_agent()

APP_NAME = "FunEnglishLearning"

# 创建Runner
runner = InMemoryRunner(
    agent=agent,
    app_name=APP_NAME
)

# 会话服务
# await runner.session_service = InMemorySessionService()

class SSEGenerator:
    """SSE事件生成器"""
    def __init__(self):
        self.event_id = 0
    
    def generate_sse_event(self, data: dict, event_type: str = "message") -> str:
        """生成SSE格式的事件"""
        self.event_id += 1
        event = {
            "id": self.event_id,
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }
        return f"id: {self.event_id}\nevent: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

sse_generator = SSEGenerator()

async def agent_stream_generator(user_input: str, session_id: str, user_id: str) -> AsyncGenerator:
    """生成Agent响应的流式数据"""
    try:
        logger.info(f"处理用户消息: {user_input[:50]}...")
        logger.info(f"会话ID: {session_id}, 用户ID: {user_id}")
        
        # 确保会话存在
        if session_id.startswith("local_"):
            # 如果是前端生成的本地会话ID，创建新会话
            session = await runner.session_service.create_session(
                app_name="FunEnglishLearning",
                user_id=user_id
            )
            session_id = session.id
            user_id = session.user_id
            logger.info(f"创建新会话: {session_id}")
        else:
            try:
                session = await runner.session_service.get_session(
                    app_name=APP_NAME, user_id=user_id, session_id=session_id)
                logger.info(f"使用现有会话: {session_id}")
            except Exception as e:
                logger.warning(f"会话不存在，创建新会话: {e}")
                session = await runner.session_service.create_session(
                    app_name="FunEnglishLearning",
                    user_id=user_id
                )
                session_id = session.id
        
        # 创建消息内容
        content = types.Content(parts=[types.Part(text=user_input)])
        
        # 更新上下文
        english_agent.update_context(user_input)
        
        # 运行Agent（流式模式）
        run_iter = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
            run_config=RunConfig(
                streaming_mode=StreamingMode.SSE,
                response_modalities=["TEXT"],
                max_llm_calls=10,
            )
        )
        
        full_response = ""
        try:
            async for event in run_iter:
                if hasattr(event, 'content') and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_chunk = part.text
                            full_response += text_chunk
                            
                            # 发送流式数据
                            data = {
                                "text": text_chunk,
                                "session_id": session_id,
                                "event_type": "chunk"
                            }
                            yield sse_generator.generate_sse_event(data, "message")
                
                elif hasattr(event, 'agent_response'):
                    if event.agent_response and hasattr(event.agent_response, 'text'):
                        # 发送完整响应
                        data = {
                            "text": event.agent_response.text,
                            "session_id": session_id,
                            "event_type": "complete",
                            "full_response": full_response
                        }
                        yield sse_generator.generate_sse_event(data, "complete")
                        break
        
        except Exception as e:
            logger.error(f"Agent流处理错误: {e}")
            
            # 如果流处理出错，发送错误信息
            error_data = {
                "error": f"处理响应时出错: {str(e)}",
                "session_id": session_id,
                "event_type": "error",
                "full_response": full_response if full_response else "抱歉，AI助手暂时无法响应。请稍后再试。"
            }
            yield sse_generator.generate_sse_event(error_data, "error")
            return
        
        # 如果循环结束但没有收到complete事件，手动发送
        if full_response:
            data = {
                "text": full_response,
                "session_id": session_id,
                "event_type": "complete",
                "full_response": full_response
            }
            yield sse_generator.generate_sse_event(data, "complete")
        else:
            # 如果没有收到任何响应，发送默认响应
            default_response = "我收到你的消息了！让我想想怎么用英语回答你..."
            data = {
                "text": default_response,
                "session_id": session_id,
                "event_type": "complete",
                "full_response": default_response
            }
            yield sse_generator.generate_sse_event(data, "complete")
    
    except Exception as e:
        print_exception_stack(e, "Agent流生成器错误")
        logger.error(f"Agent流生成器错误: {e}")
        
        error_data = {
            "error": f"系统错误: {str(e)}",
            "event_type": "error"
        }
        yield sse_generator.generate_sse_event(error_data, "error")

@app.get("/", response_class=HTMLResponse)
async def get_home():
    """返回前端页面"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.post("/api/start_session")
async def start_session():
    """开始新的学习会话"""
    try:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        session = await runner.session_service.create_session(
            app_name="FunEnglishLearning",
            user_id=user_id
        )
        
        logger.info(f"创建新会话: {session.id} 用户: {user_id}")
        
        return {
            "success": True,
            "session_id": session.id,
            "user_id": user_id,
            "message": "会话创建成功"
        }
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": f"local_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            "user_id": f"user_{uuid.uuid4().hex[:8]}"
        }

@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """与英语导师对话（流式响应）"""
    try:
        data = await request.json()
        user_input = data.get("message", "").strip()
        session_id = data.get("session_id", "").strip()
        user_id = data.get("user_id", "").strip()
        
        if not user_input:
            error_data = {"error": "请输入消息"}
            return StreamingResponse(
                iter([sse_generator.generate_sse_event(error_data, "error")]),
                media_type="text/event-stream"
            )
        
        logger.info(f"收到消息 - 会话: {session_id}, 用户: {user_id}, 消息: {user_input[:50]}...")
        
        # 如果session_id为空，创建新会话
        if not session_id:
            session = await runner.session_service.create_session(
                app_name="FunEnglishLearning",
                user_id=user_id or f"user_{uuid.uuid4().hex[:8]}"
            )
            session_id = session.id
            user_id = session.user_id
        
        # 返回流式响应
        return StreamingResponse(
            agent_stream_generator(user_input, session_id, user_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    except json.JSONDecodeError:
        error_data = {"error": "请求格式错误"}
        return StreamingResponse(
            iter([sse_generator.generate_sse_event(error_data, "error")]),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"聊天接口错误: {e}")
        error_data = {"error": f"服务器错误: {str(e)}"}
        return StreamingResponse(
            iter([sse_generator.generate_sse_event(error_data, "error")]),
            media_type="text/event-stream"
        )

@app.post("/api/chat/direct")
async def chat_direct(request: Request):
    """与英语导师对话（直接响应，用于测试）"""
    try:
        data = await request.json()
        user_input = data.get("message", "").strip()
        session_id = data.get("session_id", "").strip()
        user_id = data.get("user_id", "").strip()
        
        if not user_input:
            return {"success": False, "error": "请输入消息"}
        
        # 如果session_id为空，创建新会话
        if not session_id:
            session = await runner.session_service.create_session(
                app_name="FunEnglishLearning",
                user_id=user_id or f"user_{uuid.uuid4().hex[:8]}"
            )
            session_id = session.id
            user_id = session.user_id
        elif session_id.startswith("local_"):
            # 如果是前端生成的本地ID，创建新会话
            session = await runner.session_service.create_session(
                app_name="FunEnglishLearning",
                user_id=user_id
            )
            session_id = session.id
        
        try:
            # 创建消息内容
            content = types.Content(parts=[types.Part(text=user_input)])
            
            # 更新上下文
            english_agent.update_context(user_input)
            
            # 运行Agent（非流式）
            result = runner.run(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
                run_config=RunConfig(
                    response_modalities=["TEXT"],
                    max_llm_calls=10,
                )
            )
            
            response_text = ""
            if result.agent_response and hasattr(result.agent_response, 'text'):
                response_text = result.agent_response.text
            
            return {
                "success": True,
                "response": response_text,
                "session_id": session_id,
                "user_id": user_id
            }
        
        except Exception as e:
            logger.error(f"Agent执行错误: {e}")
            return {
                "success": False,
                "error": f"AI处理错误: {str(e)}",
                "session_id": session_id,
                "user_id": user_id
            }
    
    except Exception as e:
        logger.error(f"直接聊天接口错误: {e}")
        return {
            "success": False,
            "error": f"服务器错误: {str(e)}"
        }

@app.get("/api/session/{session_id}")
async def get_session_info(user_id: str, session_id: str):
    """获取会话信息"""
    try:
        session = await runner.session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        return {
            "success": True,
            "session_id": session.id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat() if hasattr(session, 'created_at') else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 测试会话服务
        test_session = await runner.session_service.create_session(
            app_name="FunEnglishLearning",
            user_id="test_user"
        )
        await runner.session_service.get_session(app_name=APP_NAME, user_id='user_id', session_id=test_session.id)
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "english_learning",
            "await runner.session_service": "operational"
        }
    except Exception as e:
        print_exception_stack(e, "健康检查失败")
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e)
        }

@app.get("/api/test")
async def test_endpoint():
    """测试端点"""
    return {
        "status": "ok",
        "message": "服务器运行正常",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")