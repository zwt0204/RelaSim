"""
缘推 (RelaSim) API 路由

提供关系推演的核心接口：
  POST /api/relasim/run           启动一次关系推演（异步任务，返回 task_id）
  POST /api/relasim/upload        上传补充资料（对话记录等），解析为文本返回
  GET  /api/relasim/run/status    查询推演任务进度 / 结果
  GET  /api/relasim/<id>          获取已完成推演的完整结果（图谱+仿真+报告）
  POST /api/relasim/chat          与推演中的某位当事人对话
  GET  /api/relasim/history       历史推演列表
"""

import base64
import html as _html
import os
import re
import tempfile
import threading
import traceback
import zipfile
from pathlib import Path
from flask import request, jsonify

from . import relasim_bp
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale
from ..utils.file_parser import FileParser, _read_text_with_fallback
from ..utils.llm_client import LLMClient
from ..models.task import TaskManager, TaskStatus
from ..relasim import RelaSimEngine, RelaSimInput, InjectedEvent
from ..relasim.store import RelaSimStore, rebuild_graph, rebuild_simulation

logger = get_logger('relasim.api.relasim')

# 补充资料限制：单文件提取文本上限 / 随 run 提交的补充资料总量上限
UPLOAD_MAX_CHARS = 12000
ATTACHMENTS_TOTAL_CHARS = 30000
# FileParser 之外按纯文本读取的扩展（聊天记录导出常见格式）
TEXT_LIKE_EXTENSIONS = {'.csv', '.json', '.log'}
# Word 文档：docx 用 zip+XML 解析（无需额外依赖）；doc 做尽力而为的提取
DOC_EXTENSIONS = {'.docx', '.doc'}
# 图片（聊天截图等）：走视觉 LLM 转录文字
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
IMAGE_MAX_BYTES = 5 * 1024 * 1024
_IMAGE_MIME = {'.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif',
               '.bmp': 'image/bmp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def _extract_docx_text(path: str) -> str:
    """docx 本质是 zip：直接取 word/document.xml 去标签，零依赖"""
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8', 'ignore')
    xml = xml.replace('</w:p>', '\n').replace('<w:br/>', '\n').replace('<w:tab/>', '\t')
    return _html.unescape(re.sub(r'<[^>]+>', '', xml))


def _extract_doc_text(path: str) -> str:
    """旧版 .doc 尽力而为：先探 zip 魔数（很多“doc”其实是 docx 改名），
    否则按多编码解码后抽取可读文本片段，效果差时给出转存建议"""
    with open(path, 'rb') as fh:
        raw = fh.read()
    if raw[:2] == b'PK':
        return _extract_docx_text(path)
    candidates = []
    # 可读片段：CJK / CJK 标点 / 全角标点 / 弯引号 / 常见 ASCII（unicode 转义，避免引号字面量踩坑）
    pattern = re.compile(
        "[一-鿿　-〿＀-￯"
        "“”‘’A-Za-z0-9,.!?:;'\"@#\\s\\-]{6,}"
    )
    for enc in ('utf-16-le', 'gb18030', 'utf-8'):
        try:
            s = raw.decode(enc, 'ignore')
        except Exception:
            continue
        runs = [r.strip() for r in pattern.findall(s) if r.strip()]
        candidates.append('\n'.join(runs))
    best = max(candidates, key=len, default='')
    if len(best) < 30:
        raise ValueError("旧版 .doc 解析效果有限，建议另存为 .docx 或 .pdf 后再上传")
    return best


def _extract_image_text(path: str, suffix: str) -> str:
    """图片（聊天截图等）走视觉 LLM 转录文字内容"""
    if os.path.getsize(path) > IMAGE_MAX_BYTES:
        raise ValueError("图片过大（超过 5MB），请压缩后重试")
    with open(path, 'rb') as fh:
        b64 = base64.b64encode(fh.read()).decode()
    mime = _IMAGE_MIME.get(suffix, 'image/jpeg')
    client = LLMClient()
    text = client.chat(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "请把这张图片中的所有文字内容完整转录出来。"
                    "如果是聊天记录截图，请保留说话人与消息顺序（格式：说话人: 内容）。"
                    "只输出转录文本，不要任何评论或说明。"
                    "如果图片中没有文字，请简要描述图片中与人物、关系相关的信息。"
                )},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        temperature=0.1,
        max_tokens=4096,
    )
    return text


@relasim_bp.route('/upload', methods=['POST'])
def upload_material():
    """
    上传一份补充资料（multipart，字段名 file），解析为纯文本返回。
    支持 txt / md / pdf（FileParser）以及 csv / json / log（按文本读）。
    前端把解析出的文本作为 attachments 随 /run 提交。
    """
    try:
        f = request.files.get('file')
        if not f or not f.filename:
            return jsonify({"success": False, "error": "未收到文件"}), 400

        suffix = Path(f.filename).suffix.lower()
        supported = (suffix in FileParser.SUPPORTED_EXTENSIONS or suffix in TEXT_LIKE_EXTENSIONS
                     or suffix in DOC_EXTENSIONS or suffix in IMAGE_EXTENSIONS)
        if not supported:
            return jsonify({
                "success": False,
                "error": f"暂不支持的格式: {suffix or '(无后缀)'}，支持 txt / md / pdf / docx / doc / csv / json / log / 常见图片",
            }), 400

        tmp = tempfile.NamedTemporaryFile(suffix=suffix or '.txt', delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            f.save(tmp_path)
            if suffix in IMAGE_EXTENSIONS:
                text = _extract_image_text(tmp_path, suffix)
            elif suffix == '.docx':
                text = _extract_docx_text(tmp_path)
            elif suffix == '.doc':
                text = _extract_doc_text(tmp_path)
            elif suffix in TEXT_LIKE_EXTENSIONS:
                text = _read_text_with_fallback(tmp_path)
            else:
                text = FileParser.extract_text(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        text = (text or '').strip()
        if not text:
            return jsonify({"success": False, "error": "未能从文件中提取到文本"}), 400

        truncated = len(text) > UPLOAD_MAX_CHARS
        text = text[:UPLOAD_MAX_CHARS]
        logger.info(f"补充资料解析成功: {f.filename} ({len(text)} 字{'，已截断' if truncated else ''})")
        return jsonify({"success": True, "data": {
            "filename": f.filename,
            "chars": len(text),
            "truncated": truncated,
            "text": text,
        }})
    except Exception as e:
        logger.error(f"补充资料解析失败: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


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

        # 补充资料（上传解析的对话记录等）：拼入种子素材供建图谱/仿真参考
        supplement = ''
        for att in (data.get('attachments') or [])[:10]:
            try:
                name = str(att.get('name', ''))[:80]
                text = str(att.get('text', ''))[:UPLOAD_MAX_CHARS].strip()
            except AttributeError:
                continue
            if text:
                supplement += f"\n\n=== 补充资料：{name} ===\n{text}"
        if supplement:
            seed_material = seed_material + supplement[:ATTACHMENTS_TOTAL_CHARS]
            logger.info(f"随推演附带补充资料 {len(supplement)} 字")

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
                    progress_detail={"stage": "graph"},
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
                # 图谱构建完成后缓存其 dict，此后每次进度更新都随带透出，
                # 保证前端任意时刻轮询（含中途刷新页面）都能拿到图谱做回看
                graph_holder = {"graph": None}

                def on_round(r):
                    # 每轮完成推进度：图谱构建占 10%，仿真占 10~85%
                    pct = 10 + int(75 * (r.round_index + 1) / total)
                    task_manager.update_task(
                        task_id, progress=pct,
                        message=f"推演中：{r.time_label} — {r.summary[:30]}",
                        # 结构化阶段数据供前端推演流程可视化消费（无此前端回退正则）
                        progress_detail={
                            "stage": "simulating",
                            "round_index": r.round_index,
                            "total_rounds": total,
                            "time_label": r.time_label,
                            "summary": r.summary[:60],
                            "snapshot": r.snapshot,
                            "graph": graph_holder["graph"],
                        },
                    )

                def on_graph(g):
                    # 关系图谱构建完成：推进度到 10（图谱完成/仿真即将开始），
                    # 并把图谱（persons/edges/feeling）透出给前端，供推演过程中
                    # 渲染动态图谱、并可随时回看此阶段产物。
                    graph_holder["graph"] = g.to_dict()
                    task_manager.update_task(
                        task_id, progress=10,
                        message=f"关系图谱已构建：识别到 {len(g.persons)} 人 / {len(g.edges)} 段关系",
                        progress_detail={
                            "stage": "simulating",
                            "total_rounds": total,
                            "graph": graph_holder["graph"],
                        },
                    )

                output = engine.run(params, on_round=on_round, on_graph=on_graph)

                task_manager.update_task(
                    task_id, progress=90, message="正在生成关系报告...",
                    progress_detail={"stage": "report", "total_rounds": total,
                                     "graph": graph_holder["graph"]},
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
