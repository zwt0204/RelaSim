"""
缘推 (RelaSim) 离线测试

用一个 Mock LLM 客户端替换真实 LLM，不消耗任何 API 额度，
验证整条流水线（图谱构建 -> 仿真 -> 报告 -> 角色对话）的逻辑正确性：
- 数据结构解析正确
- 情感状态在多轮中被正确累加与 clamp（0~100）
- 事件注入生效
- 报告概率归一化
- 心理曲线按轮次对齐

运行：
    python backend/scripts/test_relasim_offline.py
退出码 0 表示全部通过。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.relasim import RelaSimEngine, RelaSimInput, InjectedEvent  # noqa: E402
from app.relasim.models import ScenarioType  # noqa: E402


class MockLLM:
    """
    模拟 LLM：根据 prompt 特征返回预设的结构化响应。
    通过判断 system/user 内容里的关键字来区分处于哪个阶段。
    """

    def __init__(self):
        self.round_calls = 0

    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        joined = "\n".join(m["content"] for m in messages)

        # 阶段 1：图谱构建（人设分析师）
        if "心理画像分析师" in joined:
            return {
                "context": "林然和陈默是大学同学，毕业两年的好友，林然对陈默有好感。",
                "persons": [
                    {
                        "name": "林然", "gender": "female", "age": 24,
                        "personality": "开朗外向，情绪直接",
                        "attachment_style": "anxious",
                        "values": "重视情感联结",
                        "love_history": "感情经历较少",
                        "emotional_needs": "被及时回应与重视",
                        "triggers": "被冷淡、被忽视",
                        "communication_style": "直接表达、爱倾诉",
                    },
                    {
                        "name": "陈默", "gender": "male", "age": 25,
                        "personality": "理性内敛",
                        "attachment_style": "avoidant",
                        "values": "谨慎稳妥",
                        "love_history": "上一段感情受过伤",
                        "emotional_needs": "安全感与空间",
                        "triggers": "被逼迫表态",
                        "communication_style": "回避亲密话题、用玩笑带过",
                    },
                ],
                "edges": [
                    {"source": "林然", "target": "陈默", "label": "暗恋",
                     "feeling": {"affection": 70, "trust": 80, "dependence": 60,
                                 "tension": 30, "commitment": 55}},
                    {"source": "陈默", "target": "林然", "label": "在意但犹豫",
                     "feeling": {"affection": 55, "trust": 75, "dependence": 40,
                                 "tension": 45, "commitment": 30}},
                ],
            }

        # 阶段 3：仿真每一轮（关系导演）
        if "关系导演" in joined:
            self.round_calls += 1
            # 找出两个人的 id（从 prompt 的 id 对照里粗略解析）
            # MockLLM 直接用固定升温 delta，验证累加逻辑
            saw_event = "本轮突发事件" in joined
            # 用 name=id 对照拿到 id
            import re
            ids = re.findall(r"(林然|陈默)=(\w+)", joined)
            id_map = {name: pid for name, pid in ids}
            lin = id_map.get("林然", "p_lin")
            chen = id_map.get("陈默", "p_chen")

            deltas = [
                {"source": lin, "target": chen,
                 "affection": 5, "trust": 3, "dependence": 2,
                 "tension": -2, "commitment": 4},
                {"source": chen, "target": lin,
                 "affection": 4, "trust": 2, "dependence": 1,
                 "tension": -3 if not saw_event else 8, "commitment": 3},
            ]
            narrative = "两人一起吃饭，气氛暖昧。" if not saw_event else \
                "陈默的调动消息曝光，两人陷入沉默与不安。"
            return {
                "interactions": [
                    {"scenario": "hangout", "narrative": narrative, "deltas": deltas}
                ],
                "summary": f"第{self.round_calls}轮：关系微妙升温" if not saw_event
                else f"第{self.round_calls}轮：外部压力带来紧张",
            }

        # 阶段 4：报告（关系分析师）
        if "关系分析师" in joined:
            return {
                "outcomes": [
                    {"label": "发展为恋人", "probability": 0.5, "rationale": "好感持续升温"},
                    {"label": "维持好友", "probability": 0.3, "rationale": "陈默回避"},
                    {"label": "渐行渐远", "probability": 0.2, "rationale": "异地压力"},
                ],
                "turning_points": ["第4周陈默调动消息曝光"],
                "risks": ["陈默的回避型依恋", "异地的现实压力"],
                "suggestions": ["林然可适度表达但不逼迫", "两人应就异地问题坦诚沟通"],
                "narrative": "关系整体向暖昧发展，但外部压力是关键变量。",
            }

        raise AssertionError("MockLLM 未识别的调用阶段:\n" + joined[:200])

    def chat(self, messages, temperature=0.7, max_tokens=4096, response_format=None):
        # 阶段 5：角色扮演对话
        return "（以林然的口吻）其实我一直在等他先开口……"


def _check(cond, msg):
    if not cond:
        print(f"  ✗ FAIL: {msg}")
        raise SystemExit(1)
    print(f"  ✓ {msg}")


def main():
    mock = MockLLM()
    engine = RelaSimEngine(llm_client=mock)

    params = RelaSimInput(
        seed_material="（测试用，Mock 不读取内容）",
        prediction_query="他们会在一起吗？",
        rounds=5,
        time_unit="周",
        events=[InjectedEvent(round_index=3, description="陈默的异地调动消息曝光",
                              affected_ids=[])],
    )

    print("运行离线流水线...")
    output = engine.run(params)

    print("\n[图谱]")
    _check(len(output.graph.persons) == 2, "识别出 2 个人")
    _check(len(output.graph.edges) == 2, "构建 2 条情感边")
    lin = next(p for p in output.graph.persons if p.name == "林然")
    _check(lin.attachment_style.value == "anxious", "林然依恋风格解析为 anxious")

    print("\n[仿真]")
    _check(len(output.simulation.rounds) == 5, "推演了 5 轮")
    _check(mock.round_calls == 5, "仿真调用 LLM 5 次")
    r4 = output.simulation.rounds[3]
    _check(r4.injected_event is not None, "第 4 轮注入了事件")
    _check("调动" in r4.injected_event.description, "事件内容正确")

    # 验证情感累加：林然对陈默好感初始 70，每轮 +5，5 轮后应为 95（clamp 到 100 以内）
    chen = next(p for p in output.graph.persons if p.name == "陈默")
    lin_final = next(p for p in output.simulation.final_persons if p.name == "林然")
    aff = lin_final.feelings[chen.person_id].affection
    _check(abs(aff - 95.0) < 0.01, f"林然对陈默好感累加正确 (70 + 5*5 = 95, 实得 {aff})")

    # 验证 clamp 生效：所有维度都在 [0,100]
    all_in_range = all(
        0.0 <= getattr(f, dim) <= 100.0
        for p in output.simulation.final_persons
        for f in p.feelings.values()
        for dim in ("affection", "trust", "dependence", "tension", "commitment")
    )
    _check(all_in_range, "所有情感维度均被 clamp 在 [0,100]")

    print("\n[报告]")
    _check(len(output.report.outcomes) == 3, "生成 3 种结局")
    total_prob = sum(o.probability for o in output.report.outcomes)
    _check(abs(total_prob - 1.0) < 0.01, f"结局概率归一化 (和={total_prob})")
    _check(len(output.report.risks) == 2, "识别 2 个风险点")
    _check(output.report.disclaimer != "", "报告包含免责声明")

    print("\n[心理曲线]")
    curves = output.report.psychology_curves
    _check(len(curves) == 2, "生成 2 条关系的心理曲线")
    a_curve = next(iter(curves.values()))
    _check(len(a_curve["labels"]) == 5, "曲线按 5 轮对齐")
    _check(len(a_curve["affection"]) == 5, "好感序列有 5 个数据点")

    print("\n[角色对话]")
    reply = engine.chat_with_person(
        output.graph, output.simulation,
        lin.person_id, "你现在怎么想的？",
    )
    _check(len(reply) > 0, "角色能回复")

    print("\n" + "=" * 50)
    print("✓ 全部离线测试通过")
    print("=" * 50)


if __name__ == "__main__":
    main()
