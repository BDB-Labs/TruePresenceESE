# TruePresence Telegram Community Signals

## Purpose

Telegram is treated as a community-surface integrity layer. The first-pass community signal set focuses on metadata-only behavior: join timing, posting cadence, link/media presence flags, peer synchronization, and group-hopping summaries.

These signals support review and recommended actions. They do not prove that an account is automated or agent controlled.

## Privacy Boundary

Community-surface detection must not store message bodies, captions, media files, media previews, or raw media identifiers. Link detection uses Telegram entity metadata such as `url` or `text_link` presence, not URL text extraction from message bodies.

### What is NOT stored

- Message text content
- Captions
- Media file identifiers (file_id)
- Media payloads or previews
- Raw Telegram update bodies
- Raw pointer trails (not applicable to Telegram)

### What IS stored (metadata only)

- Join timestamps (relative latency in ms)
- Message timing intervals (aggregate stats)
- Link presence flags (boolean, metadata-only)
- Media presence flags (boolean, from entity type only)
- Peer counts within timing windows
- Group-hopping counts

### Evidence Card Structure

Admin evidence cards are content-minimized. Each card contains:

- `risk`: score (0-1) and level (low/medium/high)
- `confidence`: combined detector confidence (0-1)
- `reason_codes`: list of detector reason codes
- `timestamps`: event timestamp and card creation time
- `recommended_action`: the action taken/recommended
- `feature_summaries`: aggregate TelegramCommunityFeatures values
- `detector_signals`: each signal with reason_code, severity, confidence, contribution_target, category, explanation
- `actor_refs`: user_id and group_id (metadata only)
- `surface`: always "telegram"
- `privacy_boundary`: explicitly set to "metadata_only_no_content_preview"

No content preview is included. The `message_text`, `original_message`, and raw `update` fields are excluded from review data.

### Review Data Privacy

When admin review is triggered:

- **Safety escalation reviews**: Store only evidence card, actor refs, and reason codes.
- **Community behavior reviews**: Store metadata-only user info (id, username), chat info (id, title), Telegram refs (chat_id, message_id, sender_id), reason codes, and evidence card.
- **Never stored**: message text, captions, media IDs, raw update bodies, original_message.

## Feature Model

`TelegramCommunityFeatures` (`truepresence/surfaces/telegram/community.py`) contains derived metrics only with `model_config = ConfigDict(extra="forbid")`:

| Field | Type | Description |
|-------|------|-------------|
| `join_to_first_message_ms` | float | Milliseconds from join to first message |
| `join_to_first_media_ms` | float | Milliseconds from join to first media |
| `join_to_first_link_ms` | float | Milliseconds from join to first link entity |
| `message_count_window` | int | Message count in rolling window |
| `burst_count` | int | Count of intervals <= 2000ms within window |
| `mean_message_interval_ms` | float | Mean interval between messages |
| `message_interval_stddev_ms` | float | Stddev of message intervals |
| `joined_within_cluster_count` | int | Users who joined within 60s cluster |
| `synchronized_peer_count` | int | Distinct peers posting within 3s window |
| `group_hop_count` | int | Distinct groups the user has joined |
| `link_present` | bool | Current message has link entity (metadata only) |
| `media_present` | bool | Current message has media (metadata only) |

The adapter (`truepresence/adapters/telegram.py`) records only rolling timestamps, counters, distinct group identifiers, and presence flags needed to produce these summaries.

## Detector Families

All detectors live in `truepresence/detectors/telegram_community.py`. Each emits a `DetectorSignal` with reason code, severity, confidence, contribution_target, category, and explanation.

### 1. Join-to-Action Plausibility

- **Reason code**: `join_to_action_plausibility`
- **Contribution target**: `automation`
- **Category**: `session_continuity`
- **Triggers**: first observed action within 10s of join
- **High severity**: latency <= 1500ms (confidence 0.78)
- **Medium severity**: latency 1501-10000ms (confidence 0.62)

### 2. Instant Post After Join

- **Reason code**: `instant_post_after_join`
- **Contribution target**: `automation`
- **Category**: `session_continuity`
- **Triggers**: first message within 3s of join
- **High severity**: latency <= 1000ms (confidence 0.84)
- **Medium severity**: latency 1001-3000ms (confidence 0.70)

### 3. Link Drop After Join

- **Reason code**: `link_drop_after_join`
- **Contribution target**: `automation`
- **Category**: `environment`
- **Triggers**: link entity present, first link within 30s of join
- **High severity**: latency <= 5000ms (confidence 0.82)
- **Medium severity**: latency 5001-30000ms (confidence 0.68)

### 4. Message Burst Pattern

- **Reason code**: `message_burst_pattern`
- **Contribution target**: `automation`
- **Category**: `session_continuity`
- **Triggers**: message_count >= 5 AND burst_count >= 4
- **High severity**: count >= 8 or burst >= 6 (confidence 0.82)
- **Medium severity**: otherwise (confidence 0.70)

### 5. Conversation Cadence Anomaly

- **Reason code**: `conversation_cadence_anomaly`
- **Contribution target**: `automation`
- **Category**: `session_continuity`
- **Triggers**: message_count >= 4 AND mean_interval <= 3000ms AND stddev <= 500ms
- **High severity**: count >= 6 AND stddev <= 150ms (confidence 0.76)
- **Medium severity**: otherwise (confidence 0.64)

### 6. Synchronized Posting Cluster

- **Reason code**: `synchronized_posting_cluster`
- **Contribution target**: `agentic_control`
- **Category**: `agentic_behavior`
- **Triggers**: synchronized_peer_count >= 2 (within 3s window)
- **High severity**: peer_count >= 4 (confidence 0.82)
- **Medium severity**: peer_count 2-3 (confidence 0.68)

### 7. Coordinated Join Pattern

- **Reason code**: `coordinated_join_pattern`
- **Contribution target**: `automation`
- **Category**: `session_continuity`
- **Triggers**: joined_within_cluster_count >= 5 (within 60s window)
- **High severity**: count >= 10 (confidence 0.82)
- **Medium severity**: count 5-9 (confidence 0.66)

### 8. Repeat Group Hopping Pattern

- **Reason code**: `repeat_group_hopping_pattern`
- **Contribution target**: `automation`
- **Category**: `environment`
- **Triggers**: group_hop_count >= 3 distinct groups
- **High severity**: hop_count >= 5 (confidence 0.78)
- **Medium severity**: hop_count 3-4 (confidence 0.64)

## Recommended Actions

Telegram community signals can elevate an otherwise allowed action into admin review when detector confidence is high enough (risk_score >= 0.65). This keeps the response evidence-backed while avoiding immediate punitive action from metadata alone.

When community signals are elevated:

- `action["community_reason_codes"]` is populated
- `action["confidence"]` is boosted to max(original, risk_score)
- `action["threat_categories"]` includes the reason codes
- If the original action was `allow`, it's upgraded to `alert_admin`

Tenant enforcement mode still applies. In `observe` mode, review or punitive recommendations are suppressed to allow-with-monitoring while preserving intended action and reason metadata.

## Testing Coverage

Tests (`tests/truepresence/test_telegram_community_signals.py`) verify:

- Join-to-action plausibility with metadata-only evidence
- Instant post after join with no content in evidence card
- Link drop after join using entity metadata only
- Message burst pattern detection from cadence only
- Conversation cadence anomaly detection
- Synchronized posting cluster without message bodies
- Coordinated join pattern detection
- Repeat group hopping pattern detection
- Media presence stored without media payload
- No captions or file IDs in evidence cards
- Evidence card has all required fields (risk, confidence, reason codes, timestamps, recommended_action)
- Review data excludes message_text, original_message, and raw update body
- Manual review evidence card includes privacy_boundary marker

## Limitations

Metadata-only signals are probabilistic and can overlap with legitimate behavior, such as:

- Live events with rapid posting
- Fast onboarding flows
- Coordinated announcements
- Accessibility-assisted workflows
- Power users with multiple group memberships
- Users responding quickly to time-sensitive content

Thresholds should be calibrated with aggregate production telemetry and reviewed per community policy. Detector confidence values are first-pass calibrations and should be tuned with production data.

The detectors do not:
- Determine if an account is actually automated or human
- Prove coordinated activity (they detect potential patterns only)
- Replace content policy enforcement where legally required
- Create persistent behavioral identity beyond rolling session windows
