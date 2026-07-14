"""
关系报告生成器

对仿真后的世界做深度分析，产出概率化的多结局预测报告：
- 多种可能结局及概率分布；
- 关键转折点时间线；
- 每个人对每个人的心理变化曲线（好感/信任/心结/投入随时间）；
- 风险点、机会点与可操作建议。

报告强制附带伦理免责声明（见 RelationReport.disclaimer）。
"""

from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction
from .models import (
    RelationGraph,
    SimulationResult,
    RelationReport,
    RelationOutcome,
)

logger = get_logger('relasim.report')


_SYSTEM_PROMPT = """你是一位资深的关系分析师，需要基于一段已经推演完成的关系仿真记录，
写出一份客观、有洞察力的关系走向预测报告。你要综合每个人的心理画像、逐轮互动叙事、
以及情感状态的变化趋势来判断。

要求：
1. 给出 3~5 种互斥的可能结局及其概率（概率之和约等于 1）。结局要具体，如
   "发展为恋人""维持深厚友谊""渐行渐远""因误会决裂"等。
2. 概率判断要有依据，写清 rationale。
3. 提炼推演过程中的关键转折点（哪一轮、发生了什么、为何关键）。
4. 指出主要风险点与可操作的建议（建议要具体、温和、非操纵性）。
5. 只输出 JSON，不要任何解释性文字。
"""


class ReportGenerator:
    """从仿真结果生成关系走向预测报告"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate(
        self, graph: RelationGraph, result: SimulationResult
    ) -> RelationReport:
        """
        生成关系走向预测报告。

        Args:
            graph: 关系图谱（用于人物姓名映射与背景）
            result: 仿真结果（所有轮次）

        Returns:
            RelationReport
        """
        logger.info(f"开始为仿真 {result.simulation_id} 生成关系报告")

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + "\n" + get_language_instruction()},
            {"role": "user", "content": self._build_prompt(graph, result)},
        ]

        data = self.llm.chat_json(messages, temperature=0.5, max_tokens=4096)

        report = RelationReport(
            simulation_id=result.simulation_id,
            outcomes=self._parse_outcomes(data.get("outcomes", [])),
            turning_points=[str(x) for x in data.get("turning_points", [])],
            psychology_curves=self._build_curves(graph, result),
            risks=[str(x) for x in data.get("risks", [])],
            suggestions=[str(x) for x in data.get("suggestions", [])],
            narrative=str(data.get("narrative", "")),
        )
        logger.info(
            f"关系报告生成完成: {len(report.outcomes)} 种结局, "
            f"{len(report.turning_points)} 个转折点"
        )
        return report

    def _build_prompt(self, graph: RelationGraph, result: SimulationResult) -> str:
        """把仿真全过程整理成给报告 LLM 的上下文"""
        id_to_name = {p.person_id: p.name for p in graph.persons}
        lines: List[str] = []

        lines.append(f"=== 关系背景 ===\n{graph.context}\n")

        lines.append("=== 人物 ===")
        for p in graph.persons:
            lines.append(
                f"[{p.name}] 依恋风格={p.attachment_style.value} "
                f"性格={p.personality} 情感需求={p.emotional_needs}"
            )

        lines.append("\n=== 逐轮推演记录 ===")
        for r in result.rounds:
            lines.append(f"\n--- {r.time_label} ---")
            if r.injected_event is not None:
                lines.append(f"[突发事件] {r.injected_event.description}")
            for record in r.interactions:
                lines.append(f"[{record.scenario.value}] {record.narrative}")
            if r.summary:
                lines.append(f"[小结] {r.summary}")

        lines.append("\n=== 情感状态变化（首轮 -> 末轮）===")
        lines.append(self._describe_trends(graph, result, id_to_name))

        lines.append(
            "\n=== 任务 ===\n"
            "请严格按以下 JSON 结构输出：\n"
            "{\n"
            '  "outcomes": [\n'
            '    {"label": "结局名称", "probability": 0~1 的小数, "rationale": "判断依据"}\n'
            "  ],\n"
            '  "turning_points": ["转折点1（含发生在第几轮）", "..."],\n'
            '  "risks": ["风险点1", "..."],\n'
            '  "suggestions": ["建议1", "..."],\n'
            '  "narrative": "对整段关系走向的总体叙事分析"\n'
            "}"
        )
        return "\n".join(lines)

    @staticmethod
    def _describe_trends(
        graph: RelationGraph,
        result: SimulationResult,
        id_to_name: Dict[str, str],
    ) -> str:
        """对比首末轮快照，描述每条关系的情感走向"""
        if not result.rounds:
            return "（无推演数据）"
        first = result.rounds[0].snapshot
        last = result.rounds[-1].snapshot
        lines: List[str] = []
        for key in last:
            if "->" not in key:
                continue
            src_id, tgt_id = key.split("->", 1)
            sname = id_to_name.get(src_id, src_id)
            tname = id_to_name.get(tgt_id, tgt_id)
            a0 = first.get(key, {}).get("affection", "?")
            a1 = last.get(key, {}).get("affection", "?")
            t0 = first.get(key, {}).get("tension", "?")
            t1 = last.get(key, {}).get("tension", "?")
            lines.append(
                f"  {sname}->{tname}: 好感 {a0}->{a1}, 心结 {t0}->{t1}"
            )
        return "\n".join(lines)

    @staticmethod
    def _build_curves(
        graph: RelationGraph, result: SimulationResult
    ) -> Dict[str, Any]:
        """
        把每轮快照整理成可绘制的心理曲线。
        结构: { "A对B": {"labels": [...], "affection": [...], "trust": [...], ...} }
        """
        id_to_name = {p.person_id: p.name for p in graph.persons}
        curves: Dict[str, Any] = {}
        dims = ("affection", "trust", "dependence", "tension", "commitment")

        labels = [r.time_label for r in result.rounds]
        for r in result.rounds:
            for key, feeling in r.snapshot.items():
                if "->" not in key:
                    continue
                src_id, tgt_id = key.split("->", 1)
                sname = id_to_name.get(src_id, src_id)
                tname = id_to_name.get(tgt_id, tgt_id)
                label = f"{sname}对{tname}"
                series = curves.setdefault(
                    label, {"labels": labels, **{d: [] for d in dims}}
                )
                for d in dims:
                    series[d].append(feeling.get(d))
        return curves

    @staticmethod
    def _parse_outcomes(raw: List[Dict[str, Any]]) -> List[RelationOutcome]:
        outcomes: List[RelationOutcome] = []
        for item in raw:
            try:
                prob = float(item.get("probability", 0.0))
            except (TypeError, ValueError):
                prob = 0.0
            outcomes.append(
                RelationOutcome(
                    label=str(item.get("label", "")),
                    probability=max(0.0, min(1.0, prob)),
                    rationale=str(item.get("rationale", "")),
                )
            )
        # 概率归一化（若 LLM 给的和不为 1）
        total = sum(o.probability for o in outcomes)
        if total > 0:
            for o in outcomes:
                o.probability = round(o.probability / total, 3)
        return outcomes
