from pathlib import Path
from typing import Any, Dict, List

import yaml

from truepresence.adapter.evidence_adapter import EvidenceAdapter
from truepresence.core.events import Event
from truepresence.core.roles.base import (
    AdversarialRole,
    LivenessRole,
    MediationRole,
    RelayRole,
    SynthesizerRole,
)

# Default config path anchored to the repo root, not the process cwd
_DEFAULT_CONFIG = Path(__file__).parent.parent / "config.yaml"

class ESEEnsembleRuntime:
    """
    The True ESE Integration: Orchestrates the role-based pipeline.
    
    Uses unified Role interface for consistent method signatures.
    """
    def __init__(self, config_path: str = None):
        config_path = Path(config_path) if config_path else _DEFAULT_CONFIG
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self.adapter = EvidenceAdapter(self.config)
        
        # Initialize roles using unified interface
        self.liveness_analyst = LivenessRole()
        self.relay_analyst = RelayRole()
        self.mediation_analyst = MediationRole()
        self.adversarial_reviewer = AdversarialRole()
        self.synthesizer = SynthesizerRole()
        
        # Map for ESE compatibility
        self._role_map = {
            "liveness": self.liveness_analyst,
            "relay": self.relay_analyst,
            "mediation": self.mediation_analyst,
            "adversarial": self.adversarial_reviewer,
            "synthesizer": self.synthesizer
        }
        
    def evaluate(self, session_id: str, events: List[Event]) -> Dict[str, Any]:
        # 1. Adapter: Raw Events -> Evidence Bundle
        evidence = self.adapter.transform(session_id, events)
        
        # 2. Specialists: Evidence -> Individual Findings (using unified interface)
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
