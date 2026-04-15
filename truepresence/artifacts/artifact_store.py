from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List


class ArtifactStore:
    def __init__(self):
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

    def store_evidence_packet(self, packet: Any) -> None:
        self.evidence_packets.append(self._to_dict(packet))

    def store_argument_graph(self, graph: Any) -> None:
        self.argument_graphs.append(self._to_dict(graph))

    def store_role_reports(self, reports: List[Any]) -> None:
        for report in reports or []:
            self.role_reports.append(self._to_dict(report))

    def store_decision_artifact(self, artifact: Dict[str, Any]) -> None:
        self.decision_artifacts.append(dict(artifact))
