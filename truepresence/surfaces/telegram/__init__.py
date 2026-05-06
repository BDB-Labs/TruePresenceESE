from __future__ import annotations

__all__ = [
    "TelegramAdapter",
    "TelegramGuardAdapter",
    "TelegramCommunityFeatures",
    "build_telegram_community_evidence_card",
]


def __getattr__(name: str):
    if name in {"TelegramAdapter", "TelegramGuardAdapter"}:
        from .adapter import TelegramAdapter, TelegramGuardAdapter

        return {
            "TelegramAdapter": TelegramAdapter,
            "TelegramGuardAdapter": TelegramGuardAdapter,
        }[name]
    if name in {"TelegramCommunityFeatures", "build_telegram_community_evidence_card"}:
        from .community import (
            TelegramCommunityFeatures,
            build_telegram_community_evidence_card,
        )

        return {
            "TelegramCommunityFeatures": TelegramCommunityFeatures,
            "build_telegram_community_evidence_card": build_telegram_community_evidence_card,
        }[name]
    raise AttributeError(name)
