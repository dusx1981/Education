"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API配置
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # 应用配置
    APP_NAME = "Fun English Learning"
    APP_VERSION = "1.0.0"
    
    # Agent配置
    AGENT_TEMPERATURE = 0.8
    AGENT_MAX_TOKENS = 1024
    
    # 会话配置
    SESSION_TIMEOUT = 3600  # 1小时
    MAX_HISTORY_MESSAGES = 50