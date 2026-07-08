"""
缘推 (RelaSim) 数据模型

对齐 MiroFish 的分层：
- Person        <- 类比 OasisAgentProfile（把"社交平台字段"换成"心理画像字段"）
- RelationGraph <- 类比 GraphInfo / Zep 关系图谱（人物为节点、情感为边）
- InjectedEvent <- 类比"上帝视角变量注入"
- SimulationResult / RelationReport <- 类比仿真结果与 ReportAgent 报告
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


class AttachmentStyle(str, Enum):
    """依恋风格（关系推演的核心心理维度）"""
    SECURE = "secure"              # 安全型
    ANXIOUS = "anxious"            # 焦虑型
    AVOIDANT = "avoidant"          # 回避型
    FEARFUL = "fearful"            # 恐惧型（混乱型）


class ScenarioType(str, Enum):
    """仿真场景类型（类比 OASIS 的双平台，这里是多生活场景）"""
    DAILY_CHAT = "daily_chat"          # 日常聊天
    HANGOUT = "hangout"                # 约见面 / 出游
    DEEP_TALK = "deep_talk"            # 深夜交心
    CONFLICT = "conflict"              # 摩擦冲突
    EXTERNAL_PRESSURE = "external"     # 外部压力（异地、家人、第三者等）
    ALONE_REFLECTION = "reflection"    # 独处时的内心活动


@dataclass
class Person:
    """
    参与推演的一个人（关系 Agent 的静态人设 + 动态情感状态）

    静态字段来自用户上传的种子材料；动态字段（feelings）在仿真过程中演化。
    """
    person_id: str
    name: str
    gender: str = "unknown"
    age: Optional[int] = None

    # 心理画像
    personality: str = ""                      # 性格自由描述 / MBTI / 大五
    attachment_style: AttachmentStyle = AttachmentStyle.SECURE
    values: str = ""                           # 价值观
    love_history: str = ""                     # 感情经历
    emotional_needs: str = ""                  # 情感需求
    triggers: str = ""                         # 雷区 / 敏感点
    communication_style: str = ""              # 表达方式

    # 对其他人的动态情感（person_id -> feeling 向量），仿真中演化
    feelings: Dict[str, "Feeling"] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["attachment_style"] = self.attachment_style.value
        d["feelings"] = {k: v.to_dict() for k, v in self.feelings.items()}
        return d


@dataclass
class Feeling:
    """一个人对另一个人的情感状态向量（0~100 连续变量）"""
    affection: float = 50.0     # 好感 / 心动
    trust: float = 50.0         # 信任
    dependence: float = 30.0    # 依赖
    tension: float = 10.0       # 紧张 / 心结
    commitment: float = 20.0    # 投入意愿

    def clamp(self) -> "Feeling":
        for f in ("affection", "trust", "dependence", "tension", "commitment"):
            v = getattr(self, f)
            setattr(self, f, max(0.0, min(100.0, float(v))))
        return self

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class RelationEdge:
    """关系图谱中的一条有向情感边（source 对 target 的初始关系）"""
    source_id: str
    target_id: str
    label: str = ""                 # 关系描述，如"暗恋""无话不谈的好友"
    feeling: Feeling = field(default_factory=Feeling)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "label": self.label,
            "feeling": self.feeling.to_dict(),
        }


@dataclass
class RelationGraph:
    """关系图谱：人物节点 + 情感边（类比 MiroFish 的 GraphRAG 图谱）"""
    graph_id: str
    persons: List[Person] = field(default_factory=list)
    edges: List[RelationEdge] = field(default_factory=list)
    context: str = ""               # 关系背景（认识多久、共同经历等）

    def person_by_id(self, pid: str) -> Optional[Person]:
        return next((p for p in self.persons if p.person_id == pid), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "context": self.context,
            "persons": [p.to_dict() for p in self.persons],
            "edges": [e.to_dict() for e in self.edges],
        }


@dataclass
class InjectedEvent:
    """上帝视角注入的关系变量（类比 MiroFish 的动态变量注入）"""
    round_index: int                 # 在第几轮注入（0-based）
    description: str                 # 事件描述，如"A 的前任突然回来找 A"
    affected_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionRecord:
    """单轮某场景下的一次互动记录"""
    scenario: ScenarioType
    narrative: str                              # 这段互动发生了什么（叙事）
    feeling_deltas: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # feeling_deltas: "source_id->target_id" -> {字段: 变化量}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario.value,
            "narrative": self.narrative,
            "feeling_deltas": self.feeling_deltas,
        }


@dataclass
class RoundResult:
    """一轮（一个时间片）的推演结果"""
    round_index: int
    time_label: str                             # 如"第 3 周"
    interactions: List[InteractionRecord] = field(default_factory=list)
    injected_event: Optional[InjectedEvent] = None
    summary: str = ""                           # 本轮关系状态小结
    snapshot: Dict[str, Any] = field(default_factory=dict)  # 本轮结束时的情感快照

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_index": self.round_index,
            "time_label": self.time_label,
            "interactions": [i.to_dict() for i in self.interactions],
            "injected_event": self.injected_event.to_dict() if self.injected_event else None,
            "summary": self.summary,
            "snapshot": self.snapshot,
        }


@dataclass
class SimulationResult:
    """整段仿真的结果（所有轮次）"""
    simulation_id: str
    graph_id: str
    rounds: List[RoundResult] = field(default_factory=list)
    final_persons: List[Person] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "created_at": self.created_at,
            "rounds": [r.to_dict() for r in self.rounds],
            "final_persons": [p.to_dict() for p in self.final_persons],
        }


@dataclass
class RelationOutcome:
    """一种可能的关系结局及其概率"""
    label: str                                  # 如"发展为恋人"
    probability: float                          # 0~1
    rationale: str = ""                         # 判断依据

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RelationReport:
    """关系走向预测报告（类比 MiroFish 的 ReportAgent 报告）"""
    simulation_id: str
    outcomes: List[RelationOutcome] = field(default_factory=list)
    turning_points: List[str] = field(default_factory=list)
    psychology_curves: Dict[str, Any] = field(default_factory=dict)
    risks: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    narrative: str = ""                         # 总体叙事
    disclaimer: str = (
        "本报告由 AI 基于你提供的信息进行虚构推演，仅供娱乐与自我觉察参考，"
        "不代表真实的人的真实想法，请勿据此对真实关系做操纵性决策。"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "turning_points": self.turning_points,
            "psychology_curves": self.psychology_curves,
            "risks": self.risks,
            "suggestions": self.suggestions,
            "narrative": self.narrative,
            "disclaimer": self.disclaimer,
        }
