"""
缘推 (RelaSim) 命令行运行脚本

用法：
    # 交互式：跟着提示输入种子材料与推演诉求
    python backend/scripts/run_relasim.py

    # 直接跑内置示例（异性好友的关系推演）
    python backend/scripts/run_relasim.py --demo

    # 从文件读取种子材料
    python backend/scripts/run_relasim.py --seed path/to/material.txt --rounds 6

依赖 .env 中的 LLM 配置（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME）。
"""

import os
import sys
import json
import argparse

# 让脚本能直接 import backend.app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.relasim import RelaSimEngine, RelaSimInput, InjectedEvent  # noqa: E402


DEMO_SEED = """
林然（女，24 岁）和陈默（男，25 岁）是大学同班同学，毕业两年一直是无话不谈的好朋友。
林然性格开朗外向，情绪表达直接，遇事喜欢找人倾诉，很在意对方的即时回应，
一旦对方冷淡就会胡思乱想。她其实这一年多渐渐对陈默动了心，但怕破坏现在的关系不敢说。
陈默偏理性内敛，习惯把感受藏在心里，遇到亲密话题会本能地转移或用玩笑带过，
他也隐约感觉到林然的心意，但因为上一段感情受过伤，对开始新关系很犹豫。
两人几乎每天都会聊天，周末常一起吃饭看电影，共同朋友都觉得他们像情侣。
最近陈默拿到了一个去另一个城市工作的 offer，还没告诉林然。
""".strip()

DEMO_QUERY = "如果接下来半年林然主动一些，他们最终会在一起还是回到纯友谊？"


def _load_seed(args) -> str:
    if args.demo:
        return DEMO_SEED
    if args.seed:
        with open(args.seed, "r", encoding="utf-8") as f:
            return f.read()
    print("请输入种子材料（描述人物与他们的关系），输入结束后按 Ctrl-D（Windows: Ctrl-Z 回车）：")
    return sys.stdin.read().strip()


def _print_report(output) -> None:
    report = output.report
    print("\n" + "=" * 60)
    print("关系走向预测报告")
    print("=" * 60)

    print("\n【可能结局】")
    for o in report.outcomes:
        print(f"  - {o.label}: {o.probability * 100:.0f}%")
        if o.rationale:
            print(f"      依据: {o.rationale}")

    print("\n【关键转折点】")
    for tp in report.turning_points:
        print(f"  - {tp}")

    print("\n【风险点】")
    for r in report.risks:
        print(f"  - {r}")

    print("\n【建议】")
    for s in report.suggestions:
        print(f"  - {s}")

    if report.narrative:
        print("\n【总体分析】")
        print(f"  {report.narrative}")

    print("\n" + "-" * 60)
    print(report.disclaimer)
    print("-" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="缘推 RelaSim 关系推演")
    parser.add_argument("--demo", action="store_true", help="运行内置示例")
    parser.add_argument("--seed", help="种子材料文件路径")
    parser.add_argument("--query", default="", help="推演诉求")
    parser.add_argument("--rounds", type=int, default=6, help="推演轮数（时间片数）")
    parser.add_argument("--time-unit", default="周", help="时间片单位（周/月）")
    parser.add_argument("--json", dest="as_json", action="store_true", help="输出完整 JSON")
    args = parser.parse_args()

    seed = _load_seed(args)
    if not seed:
        print("未提供种子材料，退出。")
        sys.exit(1)

    query = args.query or (DEMO_QUERY if args.demo else "")

    engine = RelaSimEngine()
    params = RelaSimInput(
        seed_material=seed,
        prediction_query=query,
        rounds=args.rounds,
        time_unit=args.time_unit,
    )

    def _on_round(round_result) -> None:
        print(f"  [{round_result.time_label}] {round_result.summary}")

    print("开始推演，逐轮进度：")
    output = engine.run(params, on_round=_on_round)

    if args.as_json:
        print(json.dumps(output.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(output)


if __name__ == "__main__":
    main()
