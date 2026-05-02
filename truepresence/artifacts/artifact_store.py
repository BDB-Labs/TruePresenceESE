from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from truepresence.runtime.distributed import DistributedRuntime

logger = logging.getLogger(__name__)


class ArtifactStore:
    def __init__(self, distributed_runtime: Optional[DistributedRuntime] = None):
        self.dist = distributed_runtime or DistributedRuntime()
        self.evidence_packets: List[Dict[str, Any]] = []
        self.argument_graphs: List[Dict[str, Any]] = []
        self.role_reports: List[Dict[str, Any]] = []
        self.decision_artifacts: List[Dict[str, Any]] = []

    def _to_dict(self, value: Any) -> Dict[str, Any]:
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return dict(value)
        return {"value": value}

    def _persist(self, key: str, value: Dict[str, Any]) -> None:
        update_session_field = getattr(self.dist, "update_session_field", None)
        if not callable(update_session_field):
            return
        try:
            update_session_field(key, "data", value)
        except Exception as exc:
            logger.warning("Artifact persistence unavailable for %s: %s", key, exc)

    def store_evidence_packet(self, packet: Any) -> None:
        packet_data = self._to_dict(packet)
        self.evidence_packets.append(packet_data)
        packet_id = getattr(packet, "packet_id", "unknown")
        self._persist(f"artifact:packet:{packet_id}", packet_data)

    def store_argument_graph(self, graph: Any) -> None:
        graph_data = self._to_dict(graph)
        self.argument_graphs.append(graph_data)
        graph_id = getattr(graph, "graph_id", "unknown")
        self._persist(f"artifact:graph:{graph_id}", graph_data)

    def store_role_reports(self, reports: List[Any]) -> None:
        for report in reports or []:
            report_data = self._to_dict(report)
            self.role_reports.append(report_data)
            report_id = report.get("report_id", "unknown")
            self._persist(f"artifact:report:{report_id}", report_data)

    def store_decision_artifact(self, artifact: Dict[str, Any]) -> None:
        artifact_data = dict(artifact)
        self.decision_artifacts.append(artifact_data)
        decision_id = artifact.get("decision_id", "unknown")
        self._persist(f"artifact:decision:{decision_id}", artifact_data)
