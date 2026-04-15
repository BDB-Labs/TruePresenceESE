from __future__ import annotations

import uuid
from typing import Any, Dict, List

from truepresence.core.orchestrator_v3 import TruePresenceOrchestratorV3


def _flatten_findings(raw: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    if raw.get("finding"):
        findings.append(str(raw["finding"]))
    for item in raw.get("findings", []) or []:
        findings.append(str(item))
    for item in raw.get("threat_categories", []) or []:
        findings.append(str(item))
    return list(dict.fromkeys(findings))


def _normalize_single_report(role: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    findings = _flatten_findings(raw)
    summary = raw.get("summary") or raw.get("finding") or ", ".join(findings) or f"{role} completed without a structured summary."
    return {
        "report_id": raw.get("report_id") or f"report:{role}:{uuid.uuid4()}",
        "role": role,
        "summary": summary,
        "confidence": float(raw.get("confidence", 0.5)),
        "human_probability": raw.get("human_probability"),
        "findings": findings,
        "metadata": {
            **dict(raw.get("metadata", {})),
            "raw_role_output": dict(raw),
        },
    }


def _reasoning_integrity_review(reports: List[Dict[str, Any]], payload: Dict[str, Any]) -> Dict[str, Any]:
    unsupported_claims: List[str] = []
    probabilities = [report["human_probability"] for report in reports if report.get("human_probability") is not None]
    disagreement_score = 0.0
    if probabilities:
        disagreement_score = max(probabilities) - min(probabilities)

    packet = payload.get("evidence_packet")
    challenge_status = getattr(packet, "challenge_data", {}).get("status")

    for report in reports:
        if report.get("confidence", 0.0) > 0.9 and not report.get("findings"):
            unsupported_claims.append(f"{report['role']}:high_confidence_without_findings")
        if challenge_status == "passed" and report.get("human_probability") is not None and report["human_probability"] < 0.2:
            unsupported_claims.append(f"{report['role']}:contradicts_passed_challenge")

    findings = []
    if unsupported_claims:
        findings.append("unsupported_inference_detected")
    if disagreement_score > 0.5:
        findings.append("material_role_disagreement")

    # This synthetic reviewer is a good candidate for a reasoning-optimized model later.
    return {
        "report_id": f"report:reasoning_integrity_reviewer:{uuid.uuid4()}",
        "role": "reasoning_integrity_reviewer",
        "summary": "Reviewed whether role conclusions are supported by the current evidence packet and argument graph.",
        "confidence": max(0.4, min(0.95, 0.55 + disagreement_score / 2)),
        "findings": findings,
        "metadata": {
            "disagreement_score": disagreement_score,
            "unsupported_claims": unsupported_claims,
        },
    }


def normalize_role_reports(result: Any, payload: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    if isinstance(result, list):
        for index, item in enumerate(result):
            raw = dict(item) if isinstance(item, dict) else {"value": item}
            role = raw.get("role") or f"role_{index}"
            reports.append(_normalize_single_report(role, raw))
    elif isinstance(result, dict):
        roles = result.get("roles")
        if isinstance(roles, dict):
            for role, raw in roles.items():
                reports.append(_normalize_single_report(role, dict(raw)))
        elif result:
            role = result.get("role", "ensemble")
            reports.append(_normalize_single_report(role, dict(result)))

    if payload is not None:
        reports.append(_reasoning_integrity_review(reports, payload))

    return reports


class TruePresenceEnsembleRuntime:
    """
    Product-facing adapter over the current production orchestrator.

    V1 chooses `TruePresenceOrchestratorV3` because it already integrates the
    identity graph, agent council, and distributed runtime hooks.
    """

    def __init__(self, legacy_orchestrator: Any | None = None):
        self.legacy_orchestrator = legacy_orchestrator or TruePresenceOrchestratorV3()

    @property
    def memory(self) -> Any:
        return self.legacy_orchestrator.memory

    @property
    def identity_graph(self) -> Any:
        return getattr(self.legacy_orchestrator, "identity_graph", None)

    def get_session_cluster(self, session_id: str) -> Any:
        if hasattr(self.legacy_orchestrator, "get_session_cluster"):
            return self.legacy_orchestrator.get_session_cluster(session_id)
        if self.identity_graph is not None:
            return self.identity_graph.get_session_cluster(session_id)
        return set()

    def run(self, *, evidence_packet, argument_graph, context=None, tier="tier1"):
        ctx = context or {}
        payload = {
            "evidence_packet": evidence_packet,
            "argument_graph": argument_graph,
            "context": ctx,
            "tier": tier,
            "signals": {
                "timing": evidence_packet.timing_features,
                "behavioral": evidence_packet.behavioral_features,
                "identity": evidence_packet.identity_refs,
                "challenge": evidence_packet.challenge_data,
            },
            "history": evidence_packet.session_history,
        }

        session = dict(ctx.get("session", {}))
        session.setdefault("session_id", evidence_packet.session_id)
        session.setdefault("tenant_id", evidence_packet.tenant_id)

        if hasattr(self.legacy_orchestrator, "evaluate"):
            result = self.legacy_orchestrator.evaluate(
                session_id=evidence_packet.session_id,
                session=session,
                event=evidence_packet.latest_event,
                evidence_packet=evidence_packet,
                argument_graph=argument_graph,
            )
        elif hasattr(self.legacy_orchestrator, "run"):
            try:
                result = self.legacy_orchestrator.run(
                    evidence_packet=evidence_packet,
                    argument_graph=argument_graph,
                    session=session,
                )
            except TypeError:
                result = self.legacy_orchestrator.run(payload)
        elif callable(self.legacy_orchestrator):
            result = self.legacy_orchestrator(payload)
        else:
            raise TypeError("Unsupported legacy orchestrator interface")

        return normalize_role_reports(result, payload)


TruePresenceEnsembleOrchestrator = TruePresenceEnsembleRuntime
