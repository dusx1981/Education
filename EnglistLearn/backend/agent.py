"""英语学习Agent定义"""
from google.adk.agents import LlmAgent
import os
from dotenv import load_dotenv
from google.adk.agents.run_config import RunConfig, StreamingMode

from prompt import SYSTEM_PROMPT
from qianwen import create_qwen_llm
from openai_client import create_openai_llm


# 加载环境变量
load_dotenv()

class EnglishLearningAgent:
    def __init__(self):
        # 创建英语学习Agent
        self.agent = LlmAgent(
            name="english_fun_tutor",
            model=create_openai_llm(),
            description="""
            专为初中生设计的英语学习伙伴。通过有趣的对话形式教授英语，自然融入语法和时态教学，提升学习兴趣。
            """,
            instruction=SYSTEM_PROMPT,
            output_key="learning_response",
        )
        
        # 系统上下文，跟踪学习进度
        self.context = {
            "student_level": "beginner",
            "topics_covered": [],
            "grammar_points": [],
            "vocabulary_learned": []
        }
    
    def get_agent(self):
        """获取Agent实例"""
        return self.agent
    
    def update_context(self, student_response):
        """根据学生回答更新上下文"""
        # 这里可以添加逻辑来分析学生水平
        # 简化实现：根据回答长度和复杂度调整
        if len(student_response) > 50:
            self.context["student_level"] = "intermediate"
        return self.context