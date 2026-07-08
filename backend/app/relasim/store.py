"""
缘推 (RelaSim) 结果持久化

把一次推演的完整产物（图谱 + 仿真 + 报告）以 JSON 存到磁盘，
供报告页读取、角色对话页重建上下文。仿照 report_agent 的文件存储风格，
存到 backend/uploads/relasim/<relasim_id>.json。
"""

import os
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..utils.logger import get_logger
from .models import (
    Person,
    Feeling,
    RelationGraph,
    RelationEdge,
    SimulationResult,
    AttachmentStyle,
)

logger = get_logger('mirofish.relasim.store')


# ============ 持久化 ============

_STORE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'uploads', 'relasim'
)


def _ensure_dir() -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)


class RelaSimStore:
    """推演结果的磁盘存储"""

    @staticmethod
    def save(output: Any, relasim_id: Optional[str] = None) -> Dict[str, Any]:
        """保存一次推演产物，返回记录元信息（含 relasim_id）"""
        _ensure_dir()
        relasim_id = relasim_id or f"rela_{uuid.uuid4().hex[:8]}"
        record = {
            "relasim_id": relasim_id,
            "created_at": datetime.now().isoformat(),
            "graph": output.graph.to_dict(),
            "simulation": output.simulation.to_dict(),
            "report": output.report.to_dict(),
        }
        path = os.path.join(_STORE_DIR, f"{relasim_id}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        logger.info(f"推演结果已保存: {relasim_id}")
        return record

    @staticmethod
    def load(relasim_id: str) -> Optional[Dict[str, Any]]:
        """读取一次推演产物"""
        path = os.path.join(_STORE_DIR, f"{relasim_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def list(limit: int = 20) -> List[Dict[str, Any]]:
        """列出历史推演（按创建时间倒序，返回摘要）"""
        _ensure_dir()
        records = []
        for fname in os.listdir(_STORE_DIR):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(_STORE_DIR, fname), 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                records.append({
                    "relasim_id": rec.get("relasim_id"),
                    "created_at": rec.get("created_at"),
                    "context": rec.get("graph", {}).get("context", "")[:100],
                    "person_count": len(rec.get("graph", {}).get("persons", [])),
                    "outcomes": rec.get("report", {}).get("outcomes", [])[:3],
                })
            except Exception:
                continue
        records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return records[:limit]


# ============ 从存储的 dict 重建对象（供角色对话重建上下文）============

def _rebuild_person(pd: Dict[str, Any]) -> Person:
    """从 person 的 to_dict 结果重建 Person"""
    feelings = {
        tid: Feeling(**fd) for tid, fd in pd.get("feelings", {}).items()
    }
    person = Person(
        person_id=pd["person_id"],
        name=pd["name"],
        gender=pd.get("gender", "unknown"),
        age=pd.get("age"),
        personality=pd.get("personality", ""),
        attachment_style=AttachmentStyle(pd.get("attachment_style", "secure")),
        values=pd.get("values", ""),
        love_history=pd.get("love_history", ""),
        emotional_needs=pd.get("emotional_needs", ""),
        triggers=pd.get("triggers", ""),
        communication_style=pd.get("communication_style", ""),
    )
    person.feelings = feelings
    return person


def rebuild_graph(data: Dict[str, Any]) -> RelationGraph:
    """从 to_dict 的结果重建 RelationGraph"""
    persons = [_rebuild_person(pd) for pd in data.get("persons", [])]

    edges = []
    for ed in data.get("edges", []):
        edges.append(RelationEdge(
            source_id=ed["source_id"],
            target_id=ed["target_id"],
            label=ed.get("label", ""),
            feeling=Feeling(**ed.get("feeling", {})),
        ))

    return RelationGraph(
        graph_id=data.get("graph_id", ""),
        persons=persons,
        edges=edges,
        context=data.get("context", ""),
    )


def rebuild_simulation(data: Dict[str, Any]) -> SimulationResult:
    """从 to_dict 的结果重建 SimulationResult（仅重建角色对话所需字段）"""
    result = SimulationResult(
        simulation_id=data.get("simulation_id", ""),
        graph_id=data.get("graph_id", ""),
    )
    # 角色对话只需要 final_persons，逐轮 rounds 可省略以简化
    result.final_persons = [
        _rebuild_person(pd) for pd in data.get("final_persons", [])
    ]
    return result
