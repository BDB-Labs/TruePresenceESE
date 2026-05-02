from pathlib import Path

from ese.pack_sdk import load_pack_project
from truepresence.adapter.ese_adapter import evaluate_presence
from truepresence.challenges.injector import ChallengeInjector


def test_ese_adapter_maps_truepresence_event_shape() -> None:
    result = evaluate_presence(
        {
            "event_type": "clipboard",
            "features": {
                "typing_entropy": 0.2,
                "message_velocity": 3,
            },
        }
    )

    assert result["risk_score"] > 0.4
    assert result["risk_level"] == "medium"
    assert result["decision"] == "challenge"
    assert result["evidence"]["paste_behavior"] is True


def test_challenge_injector_accepts_categorical_risk_level() -> None:
    injector = ChallengeInjector()

    assert injector.should_inject({"risk_level": "medium"}) is True
    assert injector.should_inject({"risk_level": "high"}) is False


def test_truepresence_ese_pack_manifest_loads() -> None:
    manifest = Path("truepresence/ese_bundle/truepresence_pack.yaml")
    project = load_pack_project(manifest)

    assert project.pack.key == "truepresence"
    assert [role.key for role in project.pack.roles] == [
        "liveness_analyst",
        "relay_analyst",
        "ai_mediation_analyst",
        "adversarial_reviewer",
        "trust_synthesizer",
    ]
