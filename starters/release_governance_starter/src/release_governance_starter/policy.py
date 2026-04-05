"""Release-governance starter policy checks."""

from __future__ import annotations

from ese.policy_checks import POLICY_ERROR, PolicyCheckDefinition

_SCOPE_MARKERS = ("release", "rollout", "deploy", "deployment", "cutover")


def _check_release_owner(context):
    scope = context.scope.lower()
    if not any(marker in scope for marker in _SCOPE_MARKERS):
        return []

    configured_roles = {role.lower() for role in context.role_names}
    has_release_owner = any(
        role in configured_roles
        for role in {"release_manager", "release_planner", "release_gatekeeper", "devops_sre"}
    ) or any(role.startswith("release_") for role in configured_roles)

    if has_release_owner:
        return []

    return [
        {
            "severity": POLICY_ERROR,
            "message": "Release-governance scopes require an explicit release owner.",
            "hint": "Add release_planner, release_gatekeeper, release_manager, or devops_sre before running.",
        }
    ]


def load_policy():
    """Return the release-governance starter safety policy."""
    return PolicyCheckDefinition(
        key="release-governance-safety",
        title="Release Governance Safety",
        summary="Require explicit release ownership on rollout-sensitive scopes.",
        check=_check_release_owner,
    )
