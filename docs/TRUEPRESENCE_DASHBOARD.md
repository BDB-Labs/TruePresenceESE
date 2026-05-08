# TruePresence Dashboard Evidence Cards

The TruePresence dashboard displays operational evidence as minimized cards. The cards are meant to help reviewers understand an evaluation outcome without exposing raw user content.

## Card Types

- **Web SDK evaluations** come from `/v1/truepresence/evidence/cards`, proxied by the UI at `/api/dashboard/evidence`. These cards are built from SDK evidence artifacts and include only the dashboard-safe fields.
- **Telegram evaluations** come from pending Telegram review payloads. The dashboard extracts only the evidence card, decision IDs, likelihood-style decision probabilities, reason codes, recommended action, and timestamps.
- **Safety escalations** are separated from standard Telegram evaluations when safety evidence is present. The dashboard shows the safety risk label, reason codes, recommended action, confidence, and timestamp.

## Displayed Fields

Evaluation cards may show:

- surface
- risk level or risk label
- human_presence_likelihood
- automation_likelihood
- agentic_control_likelihood
- confidence
- reason_codes
- evidence_packet_id
- decision_id, when available
- recommended_action
- timestamp

Safety escalation cards are stricter: they show risk label, reason codes, recommended action, confidence, and timestamp. They do not render media state beyond the safety label and reason codes.

## Privacy Boundary

Dashboard cards must not display raw content fields, including:

- raw typed text
- key values
- Telegram message text
- media previews
- captions
- file URLs or file IDs
- raw Telegram updates

The UI enforces this by normalizing backend payloads into a small card shape before rendering. The SDK dashboard endpoint also returns minimized card records instead of full evidence artifacts, so derived feature summaries and detector traces are not sent to the dashboard view.

## Authentication And Tenant Isolation

Dashboard evidence endpoints require authentication:

- `GET /v1/truepresence/evidence/cards`
- `GET /v1/truepresence/evidence/{evidence_packet_id}`

Tenant-scoped users can list and retrieve only evidence for their authenticated tenant. The backend derives tenant scope from the authenticated user and does not trust `tenant` or `tenant_id` query parameters by themselves. If a tenant-scoped user asks for another tenant in the card-list query, the request is rejected.

`super_admin` users may list or retrieve evidence across tenants. When an evidence artifact is missing or belongs to another tenant, tenant-scoped users receive the same not-found response so the API does not reveal whether another tenant's evidence ID exists.

The Next.js dashboard proxy at `/api/dashboard/evidence` uses the signed-in dashboard cookie and returns `401` without proxying when the cookie is absent.

## Backend Configuration

The Next.js API proxy requires `TRUEPRESENCE_API_URL` for server-side backend calls. If it is missing, routes return a clear 503 response:

`TruePresence backend URL is not configured. Set TRUEPRESENCE_API_URL for server-side proxy routes.`

The dashboard should not introduce localhost or hardcoded backend fallbacks.

## Verification

Run the standard checks from the repository root:

```bash
cd truepresence/ui && npm run lint && npm run build
cd ../.. && PYTHONPATH=. pytest tests/truepresence/test_sdk_api.py -q
git diff --check
```

Manual UI verification when no browser test harness is available:

- Sign in to `/dashboard`.
- Confirm Web SDK, Telegram evaluations, and Safety escalations are shown as separate sections.
- Confirm no card displays typed text, key values, message text, captions, file URLs, or media previews.
