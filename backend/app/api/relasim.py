"""
缘推 (RelaSim) API 路由

提供关系推演的核心接口：
  POST /api/relasim/run           启动一次关系推演（异步任务，返回 task_id）
  GET  /api/relasim/run/status    查询推演任务进度 / 结果
  GET  /api/relasim/<id>          获取已完成推演的完整结果（图谱+仿真+报告）
  POST /api/relasim/chat          与推演中的某位当事人对话
  GET  /api/relasim/history       历史推演列表
"""

import threading
import traceback
from flask import request, jsonify

from . import relasim_bp
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..relasim import RelaSimEngine, RelaSimInput, InjectedEvent
from ..relasim.store import RelaSimStore, rebuild_graph, rebuild_simulation

logger = get_logger('mirofish.api.relasim')


@relasim_bp.route('/run', methods=['POST'])
def run_simulation():
    """
    启动一次关系推演（异步）

    请求（JSON）：
        {
            "seed_material": "人物与关系的自然语言描述",  // 必填
            "prediction_query": "推演诉求",              // 可选
            "rounds": 6,                                 // 可选，默认 6
            "time_unit": "周",                           // 可选，默认 周
            "events": [                                  // 可选，上帝视角注入事件
                {"round_index": 3, "description": "...", "affected_ids": []}
            ]
        }

    返回： { success, data: { task_id } }
    """
    try:
        data = request.get_json() or {}
        seed_material = (data.get('seed_material') or '').strip()
        if not seed_material:
            return jsonify({"success": False, "error": "seed_material 不能为空"}), 400

        rounds = int(data.get('rounds', 6))
        rounds = max(1, min(rounds, 20))  # 限制 1~20 轮，避免过度消耗
        time_unit = data.get('time_unit', '周')
        prediction_query = data.get('prediction_query', '')

        # 解析注入事件
        events = []
        for ev in data.get('events', []):
            try:
                events.append(InjectedEvent(
                    round_index=int(ev.get('round_index', 0)),
                    description=str(ev.get('description', '')),
                    affected_ids=list(ev.get('affected_ids', [])),
                ))
            except (TypeError, ValueError):
                continue

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="relasim_run",
            metadata={"rounds": rounds},
        )

        current_locale = get_locale()

        def run_task():
            set_locale(current_locale)
            try:
                task_manager.update_task(
                    task_id, status=TaskStatus.PROCESSING,
                    progress=5, message="正在构建关系图谱...",
                )
                engine = RelaSimEngine()
                params = RelaSimInput(
                    seed_material=seed_material,
                    prediction_query=prediction_query,
                    rounds=rounds,
                    time_unit=time_unit,
                    events=events,
                )

                total = rounds

                def on_round(r):
                    # 每轮完成推进度：图谱构建占 10%，仿真占 10~85%
                    pct = 10 + int(75 * (r.round_index + 1) / total)
                    task_manager.update_task(
                        task_id, progress=pct,
                        message=f"推演中：{r.time_label} — {r.summary[:30]}",
                    )

                output = engine.run(params, on_round=on_round)

                task_manager.update_task(
                    task_id, progress=90, message="正在生成关系报告...",
                )

                record = RelaSimStore.save(output)
                task_manager.complete_task(task_id, result={"relasim_id": record["relasim_id"]})
            except Exception as e:
                logger.error(f"关系推演失败: {e}")
                task_manager.fail_task(task_id, str(e))

        threading.Thread(target=run_task, daemon=True).start()

        return jsonify({"success": True, "data": {"task_id": task_id}})
    except Exception as e:
        logger.error(f"启动关系推演失败: {e}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@relasim_bp.route('/run/status', methods=['GET'])
def run_status():
    """查询推演任务进度。Query: task_id"""
    try:
        task_id = request.args.get('task_id')
        if not task_id:
            return jsonify({"success": False, "error": "task_id 不能为空"}), 400
        task = TaskManager().get_task(task_id)
        if not task:
            return jsonify({"success": False, "error": "任务不存在"}), 404
        return jsonify({"success": True, "data": task.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@relasim_bp.route('/<relasim_id>', methods=['GET'])
def get_result(relasim_id: str):
    """获取已完成推演的完整结果"""
    try:
        record = RelaSimStore.load(relasim_id)
        if not record:
            return jsonify({"success": False, "error": "推演结果不存在"}), 404
        return jsonify({"success": True, "data": record})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@relasim_bp.route('/chat', methods=['POST'])
def chat():
    """
    与推演中的某位当事人对话

    请求（JSON）：
        {
            "relasim_id": "rela_xxx",   // 必填
            "person_id": "p_xxxx",       // 必填
            "message": "你现在怎么想？",  // 必填
            "history": [ {"role": "user"/"assistant", "content": "..."} ]  // 可选
        }
    """
    try:
        data = request.get_json() or {}
        relasim_id = data.get('relasim_id')
        person_id = data.get('person_id')
        message = (data.get('message') or '').strip()
        history = data.get('history', [])

        if not relasim_id or not person_id or not message:
            return jsonify({"success": False, "error": "relasim_id / person_id / message 均为必填"}), 400

        record = RelaSimStore.load(relasim_id)
        if not record:
            return jsonify({"success": False, "error": "推演结果不存在"}), 404

        # 从存储的 dict 重建 graph 与 simulation 以支持角色扮演
        graph = rebuild_graph(record["graph"])
        simulation = rebuild_simulation(record["simulation"])

        engine = RelaSimEngine()
        reply = engine.chat_with_person(
            graph=graph, simulation=simulation,
            person_id=person_id, user_message=message,
            history=history,
        )
        return jsonify({"success": True, "data": {"reply": reply}})
    except Exception as e:
        logger.error(f"角色对话失败: {e}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@relasim_bp.route('/history', methods=['GET'])
def history():
    """历史推演列表"""
    try:
        limit = request.args.get('limit', 20, type=int)
        return jsonify({"success": True, "data": RelaSimStore.list(limit=limit)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
