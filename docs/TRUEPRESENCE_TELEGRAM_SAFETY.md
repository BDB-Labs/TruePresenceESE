# TruePresence Telegram Safety

## Purpose

Telegram safety escalation is a metadata-only layer for high-risk media distribution behavior. It is designed for safety teams to identify urgent review/escalation patterns without downloading, storing, previewing, or training on suspected media by default.

The system does not classify media content locally. It evaluates behavior and optional lawful-provider reference signals.

## No-Media-Retention Posture

Safety evidence stores only:

- Telegram chat id
- Telegram message id
- sender id
- timestamps
- `media_present`
- event type
- reason codes
- risk and confidence
- provider reference id and provider outcome when supplied

Safety evidence must not store media files, media URLs where avoidable, previews, thumbnails, message text, captions, or raw content. Admin evidence cards show no media preview.

## Behavior-Only Signals

The first-pass reason codes are:

- `instant_media_post_after_join`
- `media_burst_pattern`
- `rapid_delete_repost_pattern`
- `coordinated_media_distribution_cluster`
- `new_account_high_risk_media_behavior`
- `repeat_group_hopping_pattern`

These signals are derived from join timing, media-presence booleans, rolling media cadence, peer synchronization, account-age estimates, and group-hopping metadata. They are probabilistic and should be treated as escalation evidence, not certainty.

## Provider Adapter Philosophy

TruePresence exposes an optional provider adapter interface for lawful known-bad hash or risk-provider workflows. The adapter receives minimized Telegram metadata and returns provider reference IDs, outcomes, risk, and confidence.

TruePresence does not implement local CSAM classification in this layer. Provider media handling, hashing, reporting, and legal process must happen outside this default no-media-retention path.

## Escalation Flow

Safety policy can recommend:

- `quarantine_message`
- `restrict_sender`
- `admin_review`
- `mandatory_safety_escalation`

The default behavior avoids auto-ban. Safety escalations create metadata-only review records and evidence cards. Enforcement mode and tenant policy must explicitly permit stronger automated action.

Admin cards include a critical/high risk label, reason codes, timestamps, recommended action, evidence id, and Telegram references. They do not include content previews.

## Legal And Policy Caveat

Production use must follow applicable reporting obligations, law-enforcement escalation rules, platform terms, and tenant policy. This document describes a technical minimization posture, not legal advice.
