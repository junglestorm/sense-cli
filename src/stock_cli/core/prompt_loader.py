"""
提示词加载和格式化模块
"""

import logging
import os
import xml.etree.ElementTree as ET
from string import Template

logger = logging.getLogger(__name__)


class PromptLoader:
    """提示词加载器"""

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir
        self._cache = {}  # 缓存已加载的提示词

    def load_prompt(self, prompt_name: str) -> str:
        """加载XML格式的提示词模板"""
        if prompt_name in self._cache:
            return self._cache[prompt_name]

        prompt_path = os.path.join(self.prompts_dir, f"{prompt_name}.xml")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                xml_content = f.read()

            # 解析XML并转换为文本格式
            template = self._xml_to_text(xml_content)

            self._cache[prompt_name] = template
            logger.debug(f"已加载XML提示词模板: {prompt_name}")
            return template

        except FileNotFoundError:
            logger.error(f"提示词文件不存在: {prompt_path}")
            raise
        except Exception as e:
            logger.error(f"加载提示词失败: {prompt_path}, 错误: {str(e)}")
            raise

    def _xml_to_text(self, xml_content: str) -> str:
        """将XML格式的提示词转换为文本格式"""
        try:
            root = ET.fromstring(xml_content)

            # 递归提取所有文本内容
            def extract_text(element, level=0):
                text_parts = []
                indent = "  " * level

                # 处理元素自身的文本
                if element.text and element.text.strip():
                    text_parts.append(element.text.strip())

                # 处理子元素
                for child in element:
                    child_text = extract_text(child, level + 1)
                    if child_text:
                        # 根据标签类型添加格式
                        if child.tag in ["system", "context", "instructions"]:
                            text_parts.append(f"\n<{child.tag}>\n{child_text}\n</{child.tag}>")
                        elif child.tag in ["description", "task"]:
                            text_parts.append(f"{child_text}")
                        elif child.tag in ["requirement", "guideline", "note"]:
                            text_parts.append(f"- {child_text}")
                        elif child.tag == "response_trigger":
                            text_parts.append(f"\n{child_text}")
                        else:
                            text_parts.append(child_text)

                    # 处理尾部文本
                    if child.tail and child.tail.strip():
                        text_parts.append(child.tail.strip())

                return "\n".join(text_parts)

            return extract_text(root)

        except ET.ParseError as e:
            logger.error(f"XML解析失败: {e}")
            # 如果XML解析失败，返回原始内容
            return xml_content

    def format_prompt(self, prompt_name: str, **kwargs) -> str:
        """格式化提示词"""
        template = self.load_prompt(prompt_name)

        try:
            # 使用Template类进行安全的字符串替换
            prompt_template = Template(template)
            formatted_prompt = prompt_template.safe_substitute(**kwargs)

            logger.debug(f"已格式化提示词: {prompt_name}")
            return formatted_prompt

        except Exception as e:
            logger.error(f"格式化提示词失败: {prompt_name}, 错误: {str(e)}")
            logger.error(f"提供的参数: {list(kwargs.keys())}")
            raise

    def reload_prompt(self, prompt_name: str):
        """重新加载提示词（清除缓存）"""
        if prompt_name in self._cache:
            del self._cache[prompt_name]
        return self.load_prompt(prompt_name)

    def clear_cache(self):
        """清除所有缓存"""
        self._cache.clear()
        logger.info("已清除提示词缓存")


class PromptBuilder:
    """提示词构建器，用于动态构建复杂提示词"""

    def __init__(self, loader: PromptLoader):
        self.loader = loader

    def build_planner_prompt(self, task_description: str, available_tools: list) -> str:
        """构建规划器提示词"""
        tools_description = self._format_tools_list(available_tools)

        return self.loader.format_prompt(
            "planner", task_description=task_description, available_tools=tools_description
        )

    def build_react_prompt(
        self, current_task: str, scratchpad: list, available_tools: list, 
        memory_context: str = "", conversation_history: list = None
    ) -> str:
        """构建ReAct提示词"""
        tools_description = self._format_tools_list(available_tools)
        scratchpad_text = self._format_scratchpad(scratchpad)
        conversation_text = self._format_conversation_history(conversation_history or [])

        return self.loader.format_prompt(
            "react_core",
            current_task=current_task,
            scratchpad=scratchpad_text,
            available_tools=tools_description,
            memory_context=memory_context,
            conversation_history=conversation_text,
        )

    def build_summarizer_prompt(
        self, raw_content: str, data_source: str, data_type: str = "文本"
    ) -> str:
        """构建总结器提示词"""
        return self.loader.format_prompt(
            "summarizer", raw_content=raw_content, data_source=data_source, data_type=data_type
        )

    def build_synthesizer_prompt(self, original_task: str, collected_information: str) -> str:
        """构建综合分析师提示词"""
        return self.loader.format_prompt(
            "synthesizer", original_task=original_task, collected_information=collected_information
        )

    def _format_tools_list(self, tools: list) -> str:
        """格式化工具列表"""
        if not tools:
            return "无可用工具"

        tools_text = []
        for tool in tools:
            if hasattr(tool, "name") and hasattr(tool, "description"):
                tools_text.append(f"- {tool.name}: {tool.description}")
            elif isinstance(tool, dict):
                name = tool.get("name", "未知工具")
                desc = tool.get("description", "无描述")
                tools_text.append(f"- {name}: {desc}")

        return "\n".join(tools_text)

    def _format_scratchpad(self, scratchpad: list) -> str:
        """格式化思考轨迹"""
        if not scratchpad:
            return "暂无执行历史"

        return "\n".join(scratchpad)

    def _format_conversation_history(self, conversation_history: list) -> str:
        """格式化对话历史"""
        if not conversation_history:
            return "暂无对话历史"
        
        formatted_history = []
        # 显示所有传入的对话历史（截断逻辑由main.py统一处理）
        for entry in conversation_history:
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            if role == "user":
                formatted_history.append(f"用户: {content}")
            elif role == "assistant":
                formatted_history.append(f"助手: {content}")
        
        return "\n".join(formatted_history)


# 全局提示词管理器实例
prompt_loader = PromptLoader()
prompt_builder = PromptBuilder(prompt_loader)
