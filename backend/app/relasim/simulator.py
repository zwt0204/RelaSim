"""
关系仿真引擎（场景化多轮互动仿真）

设计要点：
- 动作空间为关系动作（发消息/约见面/表白/冷处理/找第三方倾诉）；
- 覆盖多生活场景（日常/约会/深谈/冲突/外部压力）；
- 引入 0~100 的连续情感状态变量，单轮互动会更新好感/信任/心结等，
  由此涌现出关系轨迹（升温 / 暧昧 / 捅破窗户纸 / 冷淡 / 决裂）。

每一轮（time slice）：
1. 若有注入事件，先应用到本轮语境；
2. LLM 扮演"关系导演"，在若干场景中推演互动，产出叙事 + 情感变化量；
3. 把情感变化量应用到每个人的 feelings 上（连续状态演化）；
4. 生成本轮小结与情感快照。
"""

import uuid
from typing import Any, Dict, List, Optional, Callable

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction
from .models import (
    Person,
    Feeling,
    RelationGraph,
    InjectedEvent,
    InteractionRecord,
    RoundResult,
    SimulationResult,
    ScenarioType,
)

logger = get_logger('relasim.simulator')


# 关系动作空间（类比 Config.OASIS_TWITTER_ACTIONS）
RELATION_ACTIONS = [
    "发消息主动联系", "约见面/出游", "深夜交心", "表白/挑明心意",
    "冷处理/回避", "找第三方倾诉", "试探对方心意", "维持现状不表态",
]


_SYSTEM_PROMPT = """你是一位洞察人心的"关系导演"，负责推演若干真实的人在一段时间内关系如何演化。
你必须严格基于每个人的心理画像（性格、依恋风格、情感需求、雷区、沟通方式）和当前的情感状态来推演，
让他们做出符合各自人格的、可信的选择——安全型更坦诚、焦虑型易患得患失、回避型会退缩、恐惧型摇摆。

你可选择的关系动作包括：{actions}。

每一轮代表一个时间片。你要：
1. 选择 1~3 个最能推动关系发展的场景进行推演；
2. 为每个场景写一段具体、有画面感的互动叙事（谁做了什么、说了什么、心里怎么想）；
3. 给出这段互动造成的情感变化量（delta，可正可负，幅度一般在 -20~+20），
   针对"某人对某人"的具体维度：affection 好感 / trust 信任 / dependence 依赖 / tension 紧张心结 / commitment 投入。

只输出 JSON，不要任何解释性文字。
""".format(actions="、".join(RELATION_ACTIONS))


class RelationSimulator:
    """多场景关系仿真引擎"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def run(
        self,
        graph: RelationGraph,
        rounds: int = 8,
        time_unit: str = "周",
        events: Optional[List[InjectedEvent]] = None,
        on_round: Optional[Callable[[RoundResult], None]] = None,
        simulation_id: Optional[str] = None,
    ) -> SimulationResult:
        """
        运行整段关系仿真。

        Args:
            graph: 关系图谱（含初始情感状态）
            rounds: 推演的时间片数量
            time_unit: 时间片单位（周/月）
            events: 上帝视角注入的事件列表
            on_round: 每轮完成的回调（用于流式进度）
            simulation_id: 可选的仿真 id

        Returns:
            SimulationResult
        """
        simulation_id = simulation_id or f"sim_{uuid.uuid4().hex[:8]}"
        events = events or []
        events_by_round: Dict[int, InjectedEvent] = {e.round_index: e for e in events}

        logger.info(
            f"开始关系仿真 {simulation_id}: {len(graph.persons)} 人, {rounds} 轮"
        )

        result = SimulationResult(simulation_id=simulation_id, graph_id=graph.graph_id)

        for i in range(rounds):
            event = events_by_round.get(i)
            round_result = self._run_round(graph, i, time_unit, event)
            result.rounds.append(round_result)
            if on_round is not None:
                on_round(round_result)
            logger.info(f"第 {i+1}/{rounds} 轮完成: {round_result.summary[:40]}")

        # 深拷贝最终人物状态
        result.final_persons = [self._clone_person(p) for p in graph.persons]
        logger.info(f"关系仿真 {simulation_id} 完成")
        return result

    def _run_round(
        self,
        graph: RelationGraph,
        round_index: int,
        time_unit: str,
        event: Optional[InjectedEvent],
    ) -> RoundResult:
        """推演一轮，并把情感变化应用回图谱"""
        time_label = f"第 {round_index + 1} {time_unit}"

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + "\n" + get_language_instruction()},
            {"role": "user", "content": self._build_round_prompt(graph, time_label, event)},
        ]

        data = self.llm.chat_json(messages, temperature=0.75, max_tokens=8192)

        interactions = self._parse_interactions(data)
        # 应用情感变化到图谱
        for record in interactions:
            self._apply_deltas(graph, record.feeling_deltas)

        round_result = RoundResult(
            round_index=round_index,
            time_label=time_label,
            interactions=interactions,
            injected_event=event,
            summary=str(data.get("summary", "")),
            snapshot=self._snapshot(graph),
        )
        return round_result

    def _build_round_prompt(
        self,
        graph: RelationGraph,
        time_label: str,
        event: Optional[InjectedEvent],
    ) -> str:
        """构造本轮推演的用户提示词（附上当前人物状态与情感）"""
        lines: List[str] = []
        lines.append(f"=== 关系背景 ===\n{graph.context}\n")

        lines.append("=== 人物档案 ===")
        for p in graph.persons:
            lines.append(
                f"[{p.name}] (id={p.person_id}) 性别={p.gender} 年龄={p.age}\n"
                f"  性格: {p.personality}\n"
                f"  依恋风格: {p.attachment_style.value}\n"
                f"  情感需求: {p.emotional_needs}\n"
                f"  雷区: {p.triggers}\n"
                f"  沟通方式: {p.communication_style}"
            )

        lines.append("\n=== 当前情感状态（0~100）===")
        for p in graph.persons:
            for target_id, feeling in p.feelings.items():
                target = graph.person_by_id(target_id)
                tname = target.name if target else target_id
                lines.append(
                    f"  {p.name} 对 {tname}: 好感={feeling.affection:.0f} "
                    f"信任={feeling.trust:.0f} 依赖={feeling.dependence:.0f} "
                    f"心结={feeling.tension:.0f} 投入={feeling.commitment:.0f}"
                )

        if event is not None:
            lines.append(
                f"\n=== 本轮突发事件（必须纳入推演）===\n{event.description}"
            )

        # 提供 id 映射，便于 LLM 在 delta 中引用
        id_map = ", ".join(f"{p.name}={p.person_id}" for p in graph.persons)

        lines.append(
            f"\n=== 任务 ===\n"
            f"现在推演「{time_label}」这段时间内他们之间发生了什么。\n"
            f"人物 id 对照：{id_map}\n\n"
            f"注意：每段 narrative 控制在 150 字以内，聚焦最关键的一次互动，不要展开长对话；\n"
            f"最多输出 3 个 interactions。务必输出完整、合法的 JSON。\n\n"
            f"请严格按以下 JSON 结构输出：\n"
            "{\n"
            '  "interactions": [\n'
            "    {\n"
            '      "scenario": "daily_chat/hangout/deep_talk/conflict/external/reflection 之一",\n'
            '      "narrative": "这段互动的具体叙事（≤150字）",\n'
            '      "deltas": [\n'
            '        {"source": "源人物id", "target": "目标人物id",\n'
            '         "affection": 变化量, "trust": 变化量, "dependence": 变化量,\n'
            '         "tension": 变化量, "commitment": 变化量}\n'
            "      ]\n"
            "    }\n"
            "  ],\n"
            '  "summary": "本轮关系状态一句话小结"\n'
            "}"
        )
        return "\n".join(lines)

    def _parse_interactions(self, data: Dict[str, Any]) -> List[InteractionRecord]:
        records: List[InteractionRecord] = []
        for raw in data.get("interactions", []):
            scenario = self._parse_scenario(raw.get("scenario"))
            deltas: Dict[str, Dict[str, float]] = {}
            for d in raw.get("deltas", []):
                src = str(d.get("source", "")).strip()
                tgt = str(d.get("target", "")).strip()
                if not src or not tgt:
                    continue
                key = f"{src}->{tgt}"
                deltas[key] = {
                    "affection": self._num(d.get("affection")),
                    "trust": self._num(d.get("trust")),
                    "dependence": self._num(d.get("dependence")),
                    "tension": self._num(d.get("tension")),
                    "commitment": self._num(d.get("commitment")),
                }
            records.append(
                InteractionRecord(
                    scenario=scenario,
                    narrative=str(raw.get("narrative", "")),
                    feeling_deltas=deltas,
                )
            )
        return records

    def _apply_deltas(
        self, graph: RelationGraph, deltas: Dict[str, Dict[str, float]]
    ) -> None:
        """把某次互动的情感变化量累加到对应人物的 feelings 上"""
        for key, changes in deltas.items():
            if "->" not in key:
                continue
            src_id, tgt_id = key.split("->", 1)
            person = graph.person_by_id(src_id)
            if person is None:
                continue
            feeling = person.feelings.get(tgt_id)
            if feeling is None:
                feeling = Feeling()
                person.feelings[tgt_id] = feeling
            feeling.affection += changes.get("affection", 0.0)
            feeling.trust += changes.get("trust", 0.0)
            feeling.dependence += changes.get("dependence", 0.0)
            feeling.tension += changes.get("tension", 0.0)
            feeling.commitment += changes.get("commitment", 0.0)
            feeling.clamp()

    @staticmethod
    def _snapshot(graph: RelationGraph) -> Dict[str, Any]:
        """当前所有情感状态的快照，用于绘制心理曲线"""
        snap: Dict[str, Any] = {}
        for p in graph.persons:
            for tgt_id, feeling in p.feelings.items():
                snap[f"{p.person_id}->{tgt_id}"] = feeling.to_dict()
        return snap

    @staticmethod
    def _clone_person(p: Person) -> Person:
        clone = Person(
            person_id=p.person_id,
            name=p.name,
            gender=p.gender,
            age=p.age,
            personality=p.personality,
            attachment_style=p.attachment_style,
            values=p.values,
            love_history=p.love_history,
            emotional_needs=p.emotional_needs,
            triggers=p.triggers,
            communication_style=p.communication_style,
        )
        clone.feelings = {
            k: Feeling(**v.to_dict()) for k, v in p.feelings.items()
        }
        return clone

    @staticmethod
    def _parse_scenario(value: Any) -> ScenarioType:
        try:
            return ScenarioType(str(value).strip().lower())
        except (ValueError, AttributeError):
            return ScenarioType.DAILY_CHAT

    @staticmethod
    def _num(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
