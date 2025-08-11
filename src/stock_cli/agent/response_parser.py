"""简化的ReAct响应解析器

依赖XML格式提示词和模型自我遵守能力，减少硬编码解析逻辑
"""

import re
import logging
from typing import Dict, Any, Optional, NamedTuple

logger = logging.getLogger(__name__)


class ParsedStep(NamedTuple):
    """解析后的ReAct步骤"""

    thought: str
    action: Optional[str]
    action_input: Dict[str, Any]
    final_answer: Optional[str]


class ResponseParser:
    """简化的响应解析器 - 主要依赖XML格式和模型遵守能力"""

    def parse(self, response: str) -> ParsedStep:
        """简化的解析方法

        Args:
            response: LLM的原始响应

        Returns:
            ParsedStep: 解析后的步骤
        """
        # 基本清理
        response = response.strip()

        # 尝试XML标签解析
        thought, action, action_input, final_answer = self._try_xml_parse(response)

        # 如果XML解析失败，回退到简单的标记解析
        if not (thought or action or final_answer):
            thought, action, action_input, final_answer = self._try_simple_parse(
                response
            )

        # 最后的兜底：直接使用响应内容
        if not (thought or action or final_answer):
            if len(response) > 10:
                # 如果看起来像最终答案，就当作最终答案
                if any(
                    keyword in response
                    for keyword in ["综上", "总结", "总体来看", "结论", "因此", "所以"]
                ):
                    final_answer = response
                    thought = "直接给出最终答案"
                else:
                    thought = response
            else:
                thought = "模型响应为空或过短"

        return ParsedStep(
            thought=thought or "",
            action=action,
            action_input=action_input or {},
            final_answer=final_answer,
        )

    def _try_xml_parse(self, response: str) -> tuple:
        """尝试XML标签解析（期望模型使用XML格式）"""
        thought = ""
        action = None
        action_input = {}
        final_answer = None

        # XML标签解析
        thought_match = re.search(
            r"<thought>(.*?)</thought>", response, re.DOTALL | re.IGNORECASE
        )
        if thought_match:
            thought = thought_match.group(1).strip()

        action_match = re.search(
            r"<action>(.*?)</action>", response, re.DOTALL | re.IGNORECASE
        )
        if action_match:
            action_content = action_match.group(1).strip()
            action, action_input = self._parse_action_simple(action_content)

        final_match = re.search(
            r"<final_answer>(.*?)</final_answer>", response, re.DOTALL | re.IGNORECASE
        )
        if final_match:
            final_answer = final_match.group(1).strip()

        return thought, action, action_input, final_answer

    def _try_simple_parse(self, response: str) -> tuple:
        """简单的关键词解析（兜底）"""
        thought = ""
        action = None
        action_input = {}
        final_answer = None

        lines = response.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测标题行
            if line.lower().startswith(("thought:", "thinking:")):
                current_section = "thought"
                thought = line.split(":", 1)[1].strip() if ":" in line else ""
                continue
            elif line.lower().startswith("action:"):
                current_section = "action"
                action_content = line.split(":", 1)[1].strip() if ":" in line else ""
                action, action_input = self._parse_action_simple(action_content)
                continue
            elif line.lower().startswith(("final answer:", "answer:")):
                current_section = "final"
                final_answer = line.split(":", 1)[1].strip() if ":" in line else ""
                continue

            # 继续添加到当前section
            if current_section == "thought":
                thought += " " + line
            elif current_section == "final":
                final_answer += " " + line

        return thought, action, action_input, final_answer

    def _parse_action_simple(
        self, action_content: str
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """简化的动作解析"""
        if not action_content:
            return None, {}

        # 尝试匹配 function_name(param=value) 格式
        match = re.match(r"(\w+)\s*\((.*?)\)", action_content)
        if match:
            action_name = match.group(1)
            params_str = match.group(2)

            # 简单的参数解析
            params = {}
            if params_str:
                # 支持 key=value 或 key="value" 格式
                for param_match in re.finditer(r"(\w+)=([^,]+)", params_str):
                    key = param_match.group(1).strip()
                    value = param_match.group(2).strip().strip("\"'")
                    params[key] = value

            return action_name, params

        # 如果不是函数调用格式，尝试作为单个工具名
        if action_content.isalnum() or "_" in action_content:
            return action_content, {}

        return None, {}
