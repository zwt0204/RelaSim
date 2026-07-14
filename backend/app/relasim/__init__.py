"""
缘推 (RelaSim) —— 人际关系发展推演模块

核心流水线（种子信息 → 数字世界 → 多智能体演化 → 变量注入 → 预测报告），
将"群体舆情推演"聚焦为"2~N 个具体的人的关系演化推演"。

轻量实现：复用现有 LLMClient / logger / Config，
不强依赖 Zep 与 OASIS，用内存关系图谱 + 场景化仿真即可运行。

对外主入口：RelaSimEngine
"""

from .models import (
    AttachmentStyle,
    Person,
    RelationEdge,
    RelationGraph,
    ScenarioType,
    InjectedEvent,
    InteractionRecord,
    RoundResult,
    SimulationResult,
    RelationOutcome,
    RelationReport,
)
from .engine import RelaSimEngine, RelaSimInput

__all__ = [
    "AttachmentStyle",
    "Person",
    "RelationEdge",
    "RelationGraph",
    "ScenarioType",
    "InjectedEvent",
    "InteractionRecord",
    "RoundResult",
    "SimulationResult",
    "RelationOutcome",
    "RelationReport",
    "RelaSimEngine",
    "RelaSimInput",
]
