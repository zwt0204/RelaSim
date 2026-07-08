"""
缘推 (RelaSim) 编排器

把整条流水线串起来（对齐 MiroFish 的五阶段工作流）：
1. 关系图谱构建   PersonaGenerator.build_graph
2. 环境与人设搭建 （已并入图谱构建；此处仅整理仿真参数）
3. 关系仿真       RelationSimulator.run
4. 报告生成       ReportGenerator.generate
5. 深度互动       chat_with_person（与"未来的某位当事人"对话）

对外主入口：RelaSimEngine.run(...) 一次跑完 1~4 步并返回完整结果。
"""

import uuid
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction
from .models import (
    Person,
    RelationGraph,
    InjectedEvent,
    RoundResult,
    SimulationResult,
    RelationReport,
)
from .persona_generator import PersonaGenerator
from .simulator import RelationSimulator
from .report_generator import ReportGenerator

logger = get_logger('mirofish.relasim.engine')


@dataclass
class RelaSimInput:
    """一次关系推演的输入参数"""
    seed_material: str                       # 种子材料：人物与关系的自然语言描述
    prediction_query: str = ""               # 推演诉求，如"如果 A 表白半年后会怎样"
    rounds: int = 8                          # 推演的时间片数量
    time_unit: str = "周"                    # 时间片单位
    events: List[InjectedEvent] = field(default_factory=list)  # 上帝视角注入的事件


@dataclass
class RelaSimOutput:
    """一次关系推演的完整产物"""
    graph: RelationGraph
    simulation: SimulationResult
    report: RelationReport

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph": self.graph.to_dict(),
            "simulation": self.simulation.to_dict(),
            "report": self.report.to_dict(),
        }


class RelaSimEngine:
    """关系推演主引擎，编排图谱构建 -> 仿真 -> 报告全流程"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        # 复用同一个 LLM 客户端，避免重复构造
        self.llm = llm_client or LLMClient()
        self.persona_generator = PersonaGenerator(self.llm)
        self.simulator = RelationSimulator(self.llm)
        self.report_generator = ReportGenerator(self.llm)

    def run(
        self,
        params: RelaSimInput,
        on_round: Optional[Callable[[RoundResult], None]] = None,
    ) -> RelaSimOutput:
        """
        执行完整推演流程。

        Args:
            params: 推演输入参数
            on_round: 每轮仿真完成的回调（用于流式进度）

        Returns:
            RelaSimOutput（图谱 + 仿真过程 + 报告）
        """
        run_id = uuid.uuid4().hex[:8]
        logger.info(f"[RelaSim {run_id}] 开始关系推演")

        # 阶段 1 + 2：构建关系图谱（含心理画像与初始情感）
        graph = self.persona_generator.build_graph(params.seed_material)

        if len(graph.persons) < 2:
            raise ValueError(
                "种子材料中至少需要能识别出 2 个人才能推演关系，"
                f"当前仅识别到 {len(graph.persons)} 人。"
            )

        # 若用户给了推演诉求，附加到图谱背景，供仿真与报告参考
        if params.prediction_query:
            graph.context = (
                f"{graph.context}\n[用户的推演诉求] {params.prediction_query}".strip()
            )

        # 阶段 3：关系仿真
        simulation = self.simulator.run(
            graph=graph,
            rounds=params.rounds,
            time_unit=params.time_unit,
            events=params.events,
            on_round=on_round,
            simulation_id=f"sim_{run_id}",
        )

        # 阶段 4：报告生成
        report = self.report_generator.generate(graph, simulation)

        logger.info(f"[RelaSim {run_id}] 关系推演完成")
        return RelaSimOutput(graph=graph, simulation=simulation, report=report)

    def chat_with_person(
        self,
        graph: RelationGraph,
        simulation: SimulationResult,
        person_id: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        阶段 5：与"仿真结束时的某位当事人"对话。

        让 LLM 扮演该角色，基于其人设与仿真终态的情感状态回答用户。

        Args:
            graph: 关系图谱
            simulation: 仿真结果（用于取终态情感）
            person_id: 要对话的人物 id
            user_message: 用户这轮说的话
            history: 之前的对话历史 [{"role": "user"/"assistant", "content": ...}]

        Returns:
            该角色的回复
        """
        person = graph.person_by_id(person_id)
        if person is None:
            # 也可能在 final_persons 里
            person = next(
                (p for p in simulation.final_persons if p.person_id == person_id),
                None,
            )
        if person is None:
            raise ValueError(f"找不到 person_id={person_id} 对应的人物")

        # 取仿真终态的该人物情感状态
        final_person = next(
            (p for p in simulation.final_persons if p.person_id == person_id),
            person,
        )

        system_prompt = self._build_roleplay_prompt(graph, simulation, final_person)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        return self.llm.chat(messages, temperature=0.85, max_tokens=1024)

    def _build_roleplay_prompt(
        self,
        graph: RelationGraph,
        simulation: SimulationResult,
        person: Person,
    ) -> str:
        """构造角色扮演的系统提示词"""
        id_to_name = {p.person_id: p.name for p in graph.persons}

        feeling_lines: List[str] = []
        for tgt_id, feeling in person.feelings.items():
            tname = id_to_name.get(tgt_id, tgt_id)
            feeling_lines.append(
                f"  你对 {tname}: 好感={feeling.affection:.0f} 信任={feeling.trust:.0f} "
                f"依赖={feeling.dependence:.0f} 心结={feeling.tension:.0f} "
                f"投入={feeling.commitment:.0f}"
            )
        feelings_block = "\n".join(feeling_lines) if feeling_lines else "  （无明确对象）"

        last_summary = simulation.rounds[-1].summary if simulation.rounds else ""

        return (
            f"你现在要扮演「{person.name}」，用第一人称与用户对话。\n"
            f"你的性格：{person.personality}\n"
            f"你的依恋风格：{person.attachment_style.value}\n"
            f"你的情感需求：{person.emotional_needs}\n"
            f"你的沟通方式：{person.communication_style}\n"
            f"你的雷区：{person.triggers}\n\n"
            f"经过这段时间的相处，你此刻的内心情感状态是：\n{feelings_block}\n\n"
            f"最近的关系状态：{last_summary}\n\n"
            "请完全代入这个人此刻的心境、语气和立场来回答，"
            "不要跳出角色，不要以 AI 的身份说话。\n"
            + get_language_instruction()
        )
