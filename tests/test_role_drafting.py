from __future__ import annotations

from ese.role_drafting import FrameworkRoleInput, draft_framework_roles


def test_draft_framework_roles_builds_prompt_and_specificity_guidance() -> None:
    review = draft_framework_roles(
        scope="Prepare a production release review",
        roles=[
            FrameworkRoleInput(
                name="Release Strategist",
                responsibility="Plan the release.",
            ),
        ],
    )

    draft = review.drafts[0]
    assert draft.key == "release_strategist"
    assert "Current scope: Prepare a production release review" in draft.prompt
    assert any("evidence" in item.lower() or "boundary" in item.lower() for item in draft.suggestions)
    assert any("short" in item.lower() for item in draft.warnings)


def test_draft_framework_roles_warns_on_overlap() -> None:
    review = draft_framework_roles(
        scope="Review a release package",
        roles=[
            FrameworkRoleInput(
                name="Risk Analyst",
                responsibility="Review rollout gating signals and produce the risk report.",
            ),
            FrameworkRoleInput(
                name="Negotiation Analyst",
                responsibility="Analyze rollout gating signals and produce the negotiation report.",
            ),
        ],
    )

    assert review.overlap_warnings
    assert "rollout" in review.overlap_warnings[0]
