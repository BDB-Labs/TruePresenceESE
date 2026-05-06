# TruePresence Telegram Community Signals

## Purpose

Telegram is treated as a community-surface integrity layer. The first-pass community signal set focuses on metadata-only behavior: join timing, posting cadence, link/media presence flags, peer synchronization, and group-hopping summaries.

These signals support review and recommended actions. They do not prove that an account is automated or agent controlled.

## Privacy Boundary

Community-surface detection must not store message bodies, captions, media files, media previews, or raw media identifiers. Link detection uses Telegram entity metadata such as `url` or `text_link` presence, not URL text extraction from message bodies.

Admin evidence cards are content-minimized. They include risk, confidence, reason codes, timestamps, recommended action, actor/group references, detector summaries, and aggregate feature values only. They do not include a content preview.

Existing tenant-configured content-policy flows may still inspect message text where already required for safe moderation. The community-surface signal layer does not add new text inspection or media storage.

## Feature Model

`TelegramCommunityFeatures` contains derived metrics only:

- `join_to_first_message_ms`
- `join_to_first_media_ms`
- `join_to_first_link_ms`
- `message_count_window`
- `burst_count`
- `mean_message_interval_ms`
- `message_interval_stddev_ms`
- `joined_within_cluster_count`
- `synchronized_peer_count`
- `group_hop_count`
- `link_present`
- `media_present`

The adapter records only rolling timestamps, counters, distinct group identifiers, and presence flags needed to produce these summaries.

## Detector Families

The initial detector families are:

- `join_to_action_plausibility`: first observed action happens shortly after a join event.
- `instant_post_after_join`: a message follows a join almost immediately.
- `link_drop_after_join`: Telegram entity metadata indicates a link shortly after join.
- `message_burst_pattern`: multiple messages land in a compact timing window.
- `conversation_cadence_anomaly`: message intervals are unusually regular over a rolling window.
- `synchronized_posting_cluster`: distinct peers post in a tight time cluster.
- `coordinated_join_pattern`: several users join the same group in a compact time cluster.
- `repeat_group_hopping_pattern`: metadata indicates the account appears across several groups.

Each detector emits a `DetectorSignal` with reason code, severity, confidence, contribution target, category, and explanation. Generic cadence and burst signals contribute to automation risk. Synchronized peer behavior can contribute to agentic-control risk when the pattern is more consistent with coordinated operation than single-account automation.

## Recommended Actions

Telegram community signals can elevate an otherwise allowed action into admin review when detector confidence is high enough. This keeps the response evidence-backed while avoiding immediate punitive action from metadata alone.

Tenant enforcement mode still applies. In `observe` mode, review or punitive recommendations are suppressed to allow-with-monitoring while preserving intended action and reason metadata.

## Limitations

Metadata-only signals are probabilistic and can overlap with legitimate behavior, such as live events, fast onboarding, coordinated announcements, or accessibility-assisted workflows. Thresholds should be calibrated with aggregate production telemetry and reviewed per community policy.
