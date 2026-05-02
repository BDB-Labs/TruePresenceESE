from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from truepresence.runtime.distributed import DistributedRuntime

logger = logging.getLogger(__name__)

class ArtifactStore:
    def __init__(self, distributed_runtime: Optional[DistributedRuntime] = None):
        self.dist = distributed_runtime or DistributedRuntime()

    def _to_dict(self, value: Any) -> Dict[str, Any]:
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return dict(value)
        return {"value": value}

    def store_evidence_packet(self, packet: Any) -> None:
        packet_id = getattr(packet, "packet_id", "unknown")
        self.dist.update_session_field(
            f"artifact:packet:{packet_id}", "data", self._to_dict(packet)
        )

    def store_argument_graph(self, graph: Any) -> None:
        graph_id = getattr(graph, "graph_id", "unknown")
        self.dist.update_session_field(
            f"artifact:graph:{graph_id}", "data", self._to_dict(graph)
        )

    def store_role_reports(self, reports: List[Any]) -> None:
        for report in reports or []:
            report_id = report.get("report_id", "unknown")
            self.dist.update_session_field(
                f"artifact:report:{report_id}", "data", self._to_dict(report)
            )

    def store_decision_artifact(self, artifact: Dict[str, Any]) -> None:
        decision_id = artifact.get("decision_id", "unknown")
        self.dist.update_session_field(
            f"artifact:decision:{decision_id}", "data", dict(artifact)
        )
