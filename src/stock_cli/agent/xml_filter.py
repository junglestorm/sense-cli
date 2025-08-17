"""XML标签过滤器状态机

专门用于从XML标签中提取内容并进行流式输出
"""

from enum import Enum
from typing import Optional, Tuple


class FilterState(Enum):
    """过滤器状态"""

    OUTSIDE = "outside"  # 在标签外
    IN_THINKING = "in_thinking"  # 在<thinking>标签内
    IN_ACTION = "in_action"  # 在<action>标签内
    IN_FINAL = "in_final"  # 在<final_answer>标签内
    SKIP_TAG = "skip_tag"  # 跳过标签本身


class XMLStreamFilter:
    """XML流式过滤状态机"""

    def __init__(self):
        self.state = FilterState.OUTSIDE
        self.buffer = ""
        self.current_tag = ""
        self.in_tag = False

    def process_chunk(self, chunk: str) -> Tuple[str, Optional[str]]:
        """处理流式chunk

        Args:
            chunk: 输入的文本片段

        Returns:
            (filtered_content, section_type): 过滤后的内容和当前section类型
        """
        result = ""
        section_type = None

        for char in chunk:
            self.buffer += char

            # 检测标签开始
            if char == "<":
                self.in_tag = True
                self.current_tag = "<"
                continue

            # 在标签中
            if self.in_tag:
                self.current_tag += char

                # 标签结束
                if char == ">":
                    self.in_tag = False
                    tag_name = self._extract_tag_name(self.current_tag)

                    if self._is_opening_tag(self.current_tag):
                        # 开始标签
                        if tag_name == "thinking":
                            self.state = FilterState.IN_THINKING
                            section_type = "thinking"
                        elif tag_name == "action":
                            self.state = FilterState.IN_ACTION
                            section_type = "action"
                        elif tag_name == "final_answer":
                            self.state = FilterState.IN_FINAL
                            section_type = "final_answer"
                    elif self._is_closing_tag(self.current_tag):
                        # 结束标签
                        if (
                            tag_name == "thinking"
                            and self.state == FilterState.IN_THINKING
                            or tag_name == "action"
                            and self.state == FilterState.IN_ACTION
                            or tag_name == "final_answer"
                            and self.state == FilterState.IN_FINAL
                        ):
                            # 结束信号：用于通知上层该段落已闭合
                            if tag_name == "final_answer":
                                section_type = "final_answer_end"
                            elif tag_name == "action":
                                section_type = "action_end"
                            elif tag_name == "thinking":
                                section_type = "thinking_end"

                            self.state = FilterState.OUTSIDE

                    self.current_tag = ""
                continue

            # 不在标签中，根据当前状态决定是否输出
            if self.state in [
                FilterState.IN_THINKING,
                FilterState.IN_ACTION,
                FilterState.IN_FINAL,
            ]:
                result += char
                if not section_type:
                    if self.state == FilterState.IN_THINKING:
                        section_type = "thinking"
                    elif self.state == FilterState.IN_ACTION:
                        section_type = "action"
                    elif self.state == FilterState.IN_FINAL:
                        section_type = "final_answer"

        return result, section_type

    def _extract_tag_name(self, tag: str) -> str:
        """从标签中提取标签名"""
        tag = tag.strip("<>")
        if tag.startswith("/"):
            tag = tag[1:]
        return tag.split()[0].lower()

    def _is_opening_tag(self, tag: str) -> bool:
        """判断是否为开始标签"""
        return not tag.strip().startswith("</")

    def _is_closing_tag(self, tag: str) -> bool:
        """判断是否为结束标签"""
        return tag.strip().startswith("</")

    def get_current_section(self) -> Optional[str]:
        """获取当前section类型"""
        if self.state == FilterState.IN_THINKING:
            return "thinking"
        elif self.state == FilterState.IN_ACTION:
            return "action"
        elif self.state == FilterState.IN_FINAL:
            return "final_answer"
        return None