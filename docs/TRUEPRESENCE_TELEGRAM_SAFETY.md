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

Safety evidence must not store media files, media URLs where avoidable, previews, thumbnails, message text, captions, file IDs, or raw content. Admin evidence cards show no media preview.

## Risk And Confidence Semantics

Safety risk and safety confidence are distinct:

- Risk answers: how concerning is the observed media-distribution pattern?
- Confidence answers: how much weight should reviewers place on this assessment?

Risk is based on the strongest concerning local behavior signal and, when present, provider risk. Confidence is intentionally more conservative. It considers the strongest detector signal confidence, provider confidence when supplied, and a small bounded corroboration bonus for multiple independent reason codes when the Telegram metadata references are sufficient.

Provider risk does not automatically become confidence. If a provider supplies high risk with moderate confidence, TruePresence preserves that distinction in the safety evidence card.

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

TruePresence exposes an optional provider adapter interface for lawful known-bad hash or risk-provider workflows. The adapter receives minimized Telegram metadata only: chat id, message id, sender id, event timestamp, event type, and media-present state. It returns provider reference IDs, outcomes, risk, and confidence.

TruePresence does not implement local CSAM classification in this layer. Provider media handling, hashing, reporting, and legal process must happen outside this default no-media-retention path.

Provider evidence inside TruePresence is reference-only. It must not include the media file, file URL, file ID, thumbnail, preview, caption, message text, or raw update payload.

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
