import yaml
from typing import Dict, Any, List
from core.events import Event
from truepresence.adapter.evidence_adapter import EvidenceAdapter
from truepresence.core.roles.liveness import LivenessAnalyst
from truepresence.core.roles.relay import RelayAnalyst
from truepresence.core.roles.mediation import MediationAnalyst
from truepresence.core.roles.adversarial import AdversarialReviewer
from truepresence.core.roles.synthesizer import TrustSynthesizer

class ESEEnsembleRuntime:
    """
    The True ESE Integration: Orchestrates the role-based pipeline.
    """
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self.adapter = EvidenceAdapter(self.config)
        self.liveness_analyst = LivenessAnalyst()
        self.relay_analyst = RelayAnalyst()
        self.mediation_analyst = MediationAnalyst()
        self.adversarial_reviewer = AdversarialReviewer()
        self.synthesizer = TrustSynthesizer()

    def evaluate(self, session_id: str, events: List[Event]) -> Dict[str, Any]:
        # 1. Adapter: Raw Events -> Evidence Bundle
        evidence = self.adapter.transform(session_id, events)
        
        # 2. Specialists: Evidence -> Individual Findings
        analysts = [
            self.liveness_analyst.analyze(evidence),
            self.relay_analyst.analyze(evidence),
            self.mediation_analyst.analyze(evidence),
        ]
        
        # 3. Adversarial Reviewer: Cross-checks all findings
        adversary = self.adversarial_reviewer.analyze(evidence, analysts)
        
        # 4. Synthesizer: Final Decision
        decision = self.synthesizer.synthesize(analysts, adversary, self.config)
        
        return {
            "session_id": session_id,
            "trust_score": decision["trust_score"],
            "decision": decision["decision"],
            "details": {
                "analysts": analysts,
                "adversary": adversary,
                "evidence": evidence["signals"]
            }
        }
