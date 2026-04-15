from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from truepresence.evidence.argument_graph import ArgumentGraph
from truepresence.evidence.packet import EvidencePacket


@dataclass
class RoleInput:
    evidence_packet: EvidencePacket
    argument_graph: ArgumentGraph
    runtime_context: Dict[str, Any]
