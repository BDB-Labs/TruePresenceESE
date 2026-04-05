"""Architecture-review starter policy checks."""

from __future__ import annotations

from ese.policy_checks import POLICY_ERROR, PolicyCheckDefinition

_SCOPE_MARKERS = ("architecture", "migration", "interface", "service boundary", "platform")


def _check_architecture_scope(context):
    scope = context.scope.lower()
    if not any(marker in scope for marker in _SCOPE_MARKERS):
        return []

    configured_roles = {role.lower() for role in context.role_names}
    has_architecture_owner = "architect" in configured_roles or any(
        role.startswith("architecture_") or role.endswith("_architect")
        for role in configured_roles
    )
    if has_architecture_owner:
        return []

    return [
        {
            "severity": POLICY_ERROR,
            "message": "Architecture-sensitive scopes require an explicit architecture owner.",
            "hint": "Add architect or an architecture_* role before running.",
        }
    ]


def load_policy():
    """Return the architecture-review starter policy."""
    return PolicyCheckDefinition(
        key="architecture-scope",
        title="Architecture Scope",
        summary="Require explicit architecture ownership for architectural or migration scopes.",
        check=_check_architecture_scope,
    )
