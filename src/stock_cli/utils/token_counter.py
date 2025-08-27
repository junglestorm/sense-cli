"""Token计算工具，使用tiktoken计算上下文token数量"""

import tiktoken
from typing import List, Dict, Any

class TokenCounter:
    """Token计数器，支持多种模型"""
    
    # 模型到编码器的映射
    MODEL_ENCODERS = {
        "gpt-4": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base", 
        "text-embedding-ada-002": "cl100k_base",
        "text-davinci-003": "p50k_base",
        "text-davinci-002": "p50k_base",
        "code-davinci-002": "p50k_base",
        "code-davinci-001": "p50k_base",
        "code-cushman-002": "p50k_base",
        "code-cushman-001": "p50k_base",
        "davinci": "r50k_base",
        "curie": "r50k_base",
        "babbage": "r50k_base",
        "ada": "r50k_base",
        "deepseek-chat": "cl100k_base",  # DeepSeek使用与GPT-4相同的编码
        "qwen": "cl100k_base",  # Qwen也使用cl100k_base
        "llama": "cl100k_base",  # Llama系列使用cl100k_base
    }
    
    @classmethod
    def get_encoding_for_model(cls, model_name: str) -> str:
        """获取模型的编码器名称"""
        # 默认使用cl100k_base，适用于大多数现代模型
        return cls.MODEL_ENCODERS.get(model_name, "cl100k_base")
    
    @classmethod
    def count_tokens(cls, text: str, model_name: str = "gpt-4") -> int:
        """计算文本的token数量"""
        try:
            encoding_name = cls.get_encoding_for_model(model_name)
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception:
            # 如果tiktoken失败，使用简单的近似计算
            return len(text) // 4  # 近似：4个字符约等于1个token
    
    @classmethod
    def count_message_tokens(cls, message: Dict[str, Any], model_name: str = "gpt-4") -> int:
        """计算单条消息的token数量"""
        content = message.get('content', '')
        if not content:
            return 0
        return cls.count_tokens(content, model_name)
    
    @classmethod
    def count_messages_tokens(cls, messages: List[Dict[str, Any]], model_name: str = "gpt-4") -> int:
        """计算消息列表的总token数量"""
        total_tokens = 0
        for message in messages:
            total_tokens += cls.count_message_tokens(message, model_name)
        return total_tokens

# 全局实例
token_counter = TokenCounter()