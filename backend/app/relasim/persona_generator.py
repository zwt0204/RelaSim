"""
人设生成器（类比 MiroFish 的 OasisProfileGenerator）

把用户上传的种子材料（自然语言描述 / 聊天记录片段）解析成结构化的
Person（心理画像）与 RelationGraph（人物节点 + 情感边）。

与 MiroFish 的区别：字段从"社交平台字段"换成"心理画像字段"，
本体从"舆情实体"换成"人际关系本体"。
"""

import uuid
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction
from .models import (
    Person,
    Feeling,
    RelationEdge,
    RelationGraph,
    AttachmentStyle,
)

logger = get_logger('mirofish.relasim.persona')


_SYSTEM_PROMPT = """你是一位资深的心理画像分析师，擅长从零散的描述中提炼一个人的性格、
依恋风格、情感需求与人际相处模式。你要把用户提供的关于若干人以及他们之间关系的种子材料，
抽取成结构化的 JSON。

要求：
1. 为每个出现的人建立一个 person 条目，推断其心理画像字段。信息缺失时基于常识做合理推断，不要留空字符串。
2. attachment_style 只能是以下之一：secure(安全型) / anxious(焦虑型) / avoidant(回避型) / fearful(恐惧型)。
3. 为每一对有互动的人建立有向情感边（A 对 B、B 对 A 各一条），feeling 各维度取值 0~100：
   - affection 好感/心动, trust 信任, dependence 依赖, tension 紧张/心结, commitment 投入意愿。
4. 只输出 JSON，不要任何解释性文字。
"""


def _build_schema_hint() -> str:
    return """请严格按以下 JSON 结构输出：
{
  "context": "关系背景总述（认识多久、共同经历、当前关系性质）",
  "persons": [
    {
      "name": "姓名或代称",
      "gender": "male/female/unknown",
      "age": 年龄数字或 null,
      "personality": "性格描述",
      "attachment_style": "secure/anxious/avoidant/fearful",
      "values": "价值观",
      "love_history": "感情经历",
      "emotional_needs": "核心情感需求",
      "triggers": "雷区/敏感点",
      "communication_style": "表达与沟通方式"
    }
  ],
  "edges": [
    {
      "source": "源人物姓名",
      "target": "目标人物姓名",
      "label": "关系描述，如 暗恋 / 无话不谈的好友",
      "feeling": {"affection": 0-100, "trust": 0-100, "dependence": 0-100, "tension": 0-100, "commitment": 0-100}
    }
  ]
}"""


class PersonaGenerator:
    """从种子材料生成关系图谱"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def build_graph(self, seed_material: str, graph_id: Optional[str] = None) -> RelationGraph:
        """
        解析种子材料，构建关系图谱。

        Args:
            seed_material: 用户提供的自然语言描述 / 聊天记录 / 关系背景
            graph_id: 可选的图谱 id

        Returns:
            RelationGraph
        """
        graph_id = graph_id or f"graph_{uuid.uuid4().hex[:8]}"
        logger.info(f"开始构建关系图谱 {graph_id}")

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + "\n" + get_language_instruction()},
            {
                "role": "user",
                "content": f"{_build_schema_hint()}\n\n=== 种子材料 ===\n{seed_material}",
            },
        ]

        data = self.llm.chat_json(messages, temperature=0.4, max_tokens=4096)
        graph = self._parse(data, graph_id)
        logger.info(
            f"关系图谱构建完成: {len(graph.persons)} 人, {len(graph.edges)} 条关系边"
        )
        return graph

    def _parse(self, data: Dict[str, Any], graph_id: str) -> RelationGraph:
        """把 LLM 返回的 JSON 转成 RelationGraph"""
        persons: List[Person] = []
        name_to_id: Dict[str, str] = {}

        for raw in data.get("persons", []):
            name = str(raw.get("name", "")).strip() or f"person_{len(persons)+1}"
            pid = f"p_{uuid.uuid4().hex[:6]}"
            name_to_id[name] = pid

            persons.append(
                Person(
                    person_id=pid,
                    name=name,
                    gender=str(raw.get("gender", "unknown")),
                    age=raw.get("age") if isinstance(raw.get("age"), int) else None,
                    personality=str(raw.get("personality", "")),
                    attachment_style=self._parse_attachment(raw.get("attachment_style")),
                    values=str(raw.get("values", "")),
                    love_history=str(raw.get("love_history", "")),
                    emotional_needs=str(raw.get("emotional_needs", "")),
                    triggers=str(raw.get("triggers", "")),
                    communication_style=str(raw.get("communication_style", "")),
                )
            )

        edges: List[RelationEdge] = []
        for raw in data.get("edges", []):
            src = name_to_id.get(str(raw.get("source", "")).strip())
            tgt = name_to_id.get(str(raw.get("target", "")).strip())
            if not src or not tgt or src == tgt:
                continue
            edge = RelationEdge(
                source_id=src,
                target_id=tgt,
                label=str(raw.get("label", "")),
                feeling=self._parse_feeling(raw.get("feeling", {})),
            )
            edges.append(edge)

        # 把初始情感边写入每个人的 feelings，作为仿真起点
        for edge in edges:
            person = next((p for p in persons if p.person_id == edge.source_id), None)
            if person is not None:
                person.feelings[edge.target_id] = self._parse_feeling(
                    edge.feeling.to_dict()
                )

        return RelationGraph(
            graph_id=graph_id,
            persons=persons,
            edges=edges,
            context=str(data.get("context", "")),
        )

    @staticmethod
    def _parse_attachment(value: Any) -> AttachmentStyle:
        try:
            return AttachmentStyle(str(value).strip().lower())
        except (ValueError, AttributeError):
            return AttachmentStyle.SECURE

    @staticmethod
    def _parse_feeling(raw: Dict[str, Any]) -> Feeling:
        def _num(key: str, default: float) -> float:
            try:
                return float(raw.get(key, default))
            except (TypeError, ValueError):
                return default

        return Feeling(
            affection=_num("affection", 50.0),
            trust=_num("trust", 50.0),
            dependence=_num("dependence", 30.0),
            tension=_num("tension", 10.0),
            commitment=_num("commitment", 20.0),
        ).clamp()
