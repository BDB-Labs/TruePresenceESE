"""
Telegram Bot Server for TruePresence

Webhook server that receives Telegram updates and processes them through
TruePresence for bot detection and group protection.

CRITICAL: This system does NOT fail silently.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from truepresence.adapters.telegram import TelegramAdapter
from truepresence.core.runtime import (
    decision_engine as shared_decision_engine,
)
from truepresence.core.runtime import (
    orchestrator as shared_orchestrator,
)
from truepresence.db import get_db

from truepresence.surfaces.telegram.adapter import TelegramGuardAdapter

# Configure logging - CRITICAL systems must log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use router instead of separate app
router = APIRouter(prefix="/telegram", tags=["telegram"])
telegram_bearer = HTTPBearer()


def _tenant_id_from_request(request: Request) -> str:
    return request.query_params.get("tenant") or request.headers.get("X-Tenant-ID", "default")


def _webhook_secret_for_tenant(tenant_id: str) -> str | None:
    return os.environ.get(f"TELEGRAM_WEBHOOK_SECRET_{tenant_id.upper()}") or os.environ.get("TELEGRAM_WEBHOOK_SECRET")


def _verify_webhook_secret(request: Request, tenant_id: str) -> None:
    expected = _webhook_secret_for_tenant(tenant_id)
    if expected and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != expected:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")


def require_telegram_admin(credentials: HTTPAuthorizationCredentials = Depends(telegram_bearer)) -> dict:  # noqa: B008
    """Require a super-admin token for Telegram management endpoints."""
    from truepresence.api.auth import ROLE_HIERARCHY, get_current_user

    user = get_current_user(credentials)
    if ROLE_HIERARCHY.get(user.get("role"), 0) < ROLE_HIERARCHY["super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class TelegramProtectionService:
    """
    Main service for Telegram group protection.

    Coordinates Telegram webhook events with TruePresence evaluation.
    Now supports multi-tenancy for different client instances.
    """

    def __init__(self, tenant_id: str = "default"):
        logger.info(f"Initializing TelegramProtectionService for tenant: {tenant_id}")

        self.tenant_id = tenant_id
        self.orchestrator = shared_orchestrator  # shared across all entry points
        self.decision_engine = shared_decision_engine
        
        # Load tenant-specific configuration
        self.tenant_config = self._load_tenant_config(tenant_id)
        self.adapter = TelegramAdapter(self.tenant_config)
        self.guard_adapter = TelegramGuardAdapter(self.decision_engine, response_adapter=self.adapter)
        self.tenant_configs: Dict[str, Dict[str, Any]] = {tenant_id: self.tenant_config}
        self.tenant_adapters: Dict[str, TelegramAdapter] = {tenant_id: self.adapter}
        self.tenant_guard_adapters: Dict[str, TelegramGuardAdapter] = {tenant_id: self.guard_adapter}
        
        # Multi-tenant data is now handled via Database (TruePresence DB)
        self.user_sessions: Dict[str, Dict[str, Any]] = {} # Transient cache for active requests
        
        # Tenant-specific configuration
        self.bot_token = self._bot_token_for_tenant(tenant_id)
        self.http_client = httpx.AsyncClient()
        
        # Tenant metadata
        self.tenant_name = os.environ.get(f"TENANT_NAME_{tenant_id.upper()}", tenant_id)
        self.tenant_created = datetime.now(timezone.utc).isoformat()

    def _bot_token_for_tenant(self, tenant_id: str) -> str | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT bot_token FROM telegram_bot_tokens WHERE tenant_id = %s", 
                    (tenant_id,)
                )
                row = cur.fetchone()
                if row:
                    return row["bot_token"]
        
        # Fallback to env vars for legacy support
        return os.environ.get(f"TELEGRAM_BOT_TOKEN_{tenant_id.upper()}") or os.environ.get("TELEGRAM_BOT_TOKEN")

    def _ensure_tenant(self, tenant_id: str) -> None:
        if tenant_id not in self.tenant_configs:
            self.tenant_configs[tenant_id] = self._load_tenant_config(tenant_id)
        if tenant_id not in self.tenant_adapters:
            adapter = TelegramAdapter(self.tenant_configs[tenant_id])
            self.tenant_adapters[tenant_id] = adapter
            self.tenant_guard_adapters[tenant_id] = TelegramGuardAdapter(self.decision_engine, response_adapter=adapter)

    def update_tenant_config(self, tenant_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_tenant(tenant_id)
        normalized = {
            "detectors": dict(config.get("detectors") or {}),
            "custom_detectors": dict(config.get("custom_detectors") or {}),
            "response_thresholds": {
                **self.tenant_configs[tenant_id].get("response_thresholds", {}),
                **dict(config.get("response_thresholds") or {}),
            },
        }
        self.tenant_configs[tenant_id] = normalized
        adapter = TelegramAdapter(normalized)
        self.tenant_adapters[tenant_id] = adapter
        self.tenant_guard_adapters[tenant_id] = TelegramGuardAdapter(self.decision_engine, response_adapter=adapter)
        return normalized

    def _load_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Load tenant-specific configuration from environment variables."""
        config = {
            "detectors": {},
            "custom_detectors": {},
            "response_thresholds": {
                "ban": 0.8,
                "kick": 0.6,
                "review": 0.4
            }
        }
        
        # Load detector configurations
        for detector in ['copyright_violation', 'torrent_sharing', 'crypto_mining', 'remote_access']:
            enabled_var = f"DETECTOR_{detector.upper()}_ENABLED_{tenant_id.upper()}"
            if enabled_var in os.environ:
                config["detectors"][detector] = {
                    "enabled": os.environ[enabled_var].lower() == "true"
                }
        
        # Load custom detector configurations
        custom_prefix = f"CUSTOM_DETECTOR_{tenant_id.upper()}_"
        for key, value in os.environ.items():
            if key.startswith(custom_prefix):
                detector_name = key[len(custom_prefix):].split('_')[0]
                if detector_name not in config["custom_detectors"]:
                    config["custom_detectors"][detector_name] = {}
                
                # Parse the rest of the key
                prop = '_'.join(key.split('_')[3:]).lower()
                if prop == "patterns":
                    # Parse patterns from JSON
                    try:
                        config["custom_detectors"][detector_name]["patterns"] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        config["custom_detectors"][detector_name]["patterns"] = [value]
                else:
                    config["custom_detectors"][detector_name][prop] = value
        
        # Load response thresholds
        for threshold in ['ban', 'kick', 'review']:
            var = f"THRESHOLD_{threshold.upper()}_{tenant_id.upper()}"
            if var in os.environ:
                try:
                    config["response_thresholds"][threshold] = float(os.environ[var])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid threshold value for {var}: {os.environ[var]}")
        
        logger.info(f"Loaded configuration for tenant {tenant_id}: {config}")
        return config
    
    async def _execute_action(self, action: Dict[str, Any], update: Dict[str, Any], tenant_id: str, decision_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the determined Telegram action via Bot API and log the outcome to ESE.
        """
        bot_token = self._bot_token_for_tenant(tenant_id)
        if not bot_token:
            return {"status": "failed", "error": "Telegram bot token not configured"}

        action_type = action.get("action")
        if action_type == "allow":
            return {"status": "executed", "action": "allow"}

        # Extract necessary IDs from update
        message = update.get("message") or update.get("edited_message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        message_id = message.get("message_id")

        if not chat_id or not user_id:
            return {"status": "failed", "error": "Missing chat or user ID in update"}

        # Map action to API endpoint and payload
        if action_type == "ban":
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            payload = {"chat_id": chat_id, "user_id": user_id}
        elif action_type == "kick":
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            payload = {
                "chat_id": chat_id, 
                "user_id": user_id, 
                "until_date": int(datetime.now(timezone.utc).timestamp()) + 60
            }
        elif action_type == "warn":
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "⚠️ Warning: Your message violated group rules.",
                "reply_to_message_id": message_id
            }
        elif action_type == "challenge":
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "🛡️ Verification Required: Please complete the challenge to continue posting.",
                "reply_to_message_id": message_id
            }
        else:
            return {"status": "skipped", "action": action_type}

        try:
            response = await self.http_client.post(url, json=payload)
            success = response.status_code == 200
            outcome = {
                "status": "success" if success else "failed",
                "action": action_type,
                "response_code": response.status_code,
                "response_text": response.text if not success else "OK",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evidence_packet_id": decision_result.get("evidence_packet", {}).get("packet_id"),
                "trace_id": decision_result.get("decision_trace_id")
            }
            
            # Log outcome back to ESE Distributed Runtime
            if hasattr(self.orchestrator, "legacy_orchestrator"):
                dist = getattr(self.orchestrator.legacy_orchestrator, "distributed", None)
                if dist and dist.available:
                    session_id = f"tg_{tenant_id}_{user_id}"
                    dist.update_session_field(session_id, "enforcement_outcome", outcome)
                    logger.info(f"[{tenant_id}] Evidence loop closed: Outcome logged for {session_id}")

            return outcome
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def process_update(self, update: Dict[str, Any], tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Process a Telegram update through TruePresence.
        """
        tenant_id = tenant_id or self.tenant_id
        self._ensure_tenant(tenant_id)
        adapter = self.tenant_adapters[tenant_id]
        guard_adapter = self.tenant_guard_adapters[tenant_id]
        
        try:
            # Parse into TruePresence event
            event = adapter.parse_update(update)
            
            if not event:
                logger.debug(f"[{tenant_id}] No relevant event to process")
                return None
            
            logger.info(f"[{tenant_id}] Processing {event['event_type']} from user {event['context'].get('user_id')}")
            
            # Get or create session for this user (tenant-isolated)
            user_id = event["context"].get("user_id", "unknown")
            session_id = f"tg_{tenant_id}_{user_id}"
            
            # Load session from DB
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT data FROM telegram_user_sessions WHERE session_id = %s", 
                        (session_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        session = json.loads(row["data"])
                    else:
                        session = {"session_id": session_id, "tenant_id": tenant_id}
                        cur.execute(
                            "INSERT INTO telegram_user_sessions (session_id, tenant_id, data) VALUES (%s, %s, %s)",
                            (session_id, tenant_id, json.dumps(session))
                        )
            
            # Evaluate with TruePresence
            decision_result = guard_adapter.evaluate_event(
                session_id=session_id,
                tenant_id=tenant_id,
                event=event,
                context={"session": session},
            )
            # Note: DecisionResult.to_response() provides the dictionary we need
            result_dict = decision_result.to_response()
            
            # Convert to Telegram action
            action = guard_adapter.enforce(decision_result.decision)
            
            logger.info(f"[{tenant_id}] Decision: {action['action']} (confidence: {action.get('confidence', 0):.2f})")
            
            # Add full result context for debugging
            action["evaluation"] = {
                "human_probability": result_dict["final"].get("human_probability"),
                "risk_factors": result_dict["final"].get("risk_factors", []),
                "reason_codes": result_dict["final"].get("reason_codes", []),
            }

            # EXECUTE the action - This makes the bot the terminating process
            execution_outcome = await self._execute_action(action, update, tenant_id, result_dict)
            action["execution"] = execution_outcome
            
            # Update session data in DB
            session["last_event_type"] = event["event_type"]
            session["last_event_timestamp"] = event["timestamp"]
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE telegram_user_sessions SET data = %s, updated_at = NOW() WHERE session_id = %s",
                        (json.dumps(session), session_id)
                    )

            # Handle manual review cases
            if action.get("action") == "alert_admin":
                await self._handle_manual_review(action, update, result_dict, tenant_id)
            
            return action
            
        except TruePresenceError as e:
            logger.error(f"[{tenant_id}] TruePresence error: {e.message}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"[{tenant_id}] UNHANDLED ERROR: {e}", exc_info=True)
            raise

        except Exception as e:
            logger.critical(f"[{tenant_id}] UNHANDLED ERROR: {e}", exc_info=True)
            raise
    
    def register_group(self, group_id: int, admin_chat_id: int = None, tenant_id: str = None):
        """Register a group for protection."""
        tenant_id = tenant_id or self.tenant_id
        self._ensure_tenant(tenant_id)
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO telegram_protected_groups (group_id, tenant_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (group_id, tenant_id)
                )
                if admin_chat_id:
                    cur.execute(
                        "INSERT INTO telegram_admin_chats (chat_id, tenant_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (admin_chat_id, tenant_id)
                    )
        logger.info(f"[{tenant_id}] Registered group {group_id} for protection in DB")

    def get_status(self, tenant_id: str = None) -> Dict[str, Any]:
        """Get service status for a tenant or all tenants."""
        tenant_id = tenant_id or self.tenant_id
        
        orch_type = "Unknown"
        if hasattr(self.orchestrator, '__class__'):
            orch_type = self.orchestrator.__class__.__name__

        if tenant_id == "all":
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT tenant_id FROM telegram_protected_groups")
                    tenants = [r["tenant_id"] for r in cur.fetchall()]
            
            tenant_statuses = {}
            for tid in tenants:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) as count FROM telegram_protected_groups WHERE tenant_id = %s", (tid,))
                        groups_count = cur.fetchone()["count"]
                        
                        cur.execute("SELECT COUNT(*) as count FROM telegram_user_sessions WHERE tenant_id = %s", (tid,))
                        sessions_count = cur.fetchone()["count"]
                        
                        cur.execute("SELECT COUNT(*) as count FROM telegram_pending_reviews WHERE tenant_id = %s AND status = 'pending'", (tid,))
                        reviews_count = cur.fetchone()["count"]
                
                tenant_statuses[tid] = {
                    "protected_groups": groups_count,
                    "active_sessions": sessions_count,
                    "pending_reviews": reviews_count,
                    "orchestrator_type": orch_type
                }
            
            return {
                "status": "healthy",
                "multi_tenant": True,
                "tenants": tenant_statuses,
                "total_tenants": len(tenant_statuses)
            }
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as count FROM telegram_protected_groups WHERE tenant_id = %s", (tenant_id,))
                    groups_count = cur.fetchone()["count"]
                    
                    cur.execute("SELECT COUNT(*) as count FROM telegram_user_sessions WHERE tenant_id = %s", (tenant_id,))
                    sessions_count = cur.fetchone()["count"]
                    
                    cur.execute("SELECT COUNT(*) as count FROM telegram_pending_reviews WHERE tenant_id = %s AND status = 'pending'", (tenant_id,))
                    reviews_count = cur.fetchone()["count"]
            
            return {
                "status": "healthy",
                "tenant_id": tenant_id,
                "protected_groups": groups_count,
                "active_sessions": sessions_count,
                "pending_reviews": reviews_count,
                "orchestrator_type": orch_type
            }


    def add_pending_review(self, review_data: Dict[str, Any], tenant_id: str = None):
        """Add a case that requires manual review."""
        tenant_id = tenant_id or self.tenant_id
        self._ensure_tenant(tenant_id)
        
        review_id = str(uuid.uuid4())
        review_data["review_id"] = review_id
        review_data["status"] = "pending"
        review_data["created_at"] = datetime.now(timezone.utc).isoformat()
        review_data["tenant_id"] = tenant_id
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO telegram_pending_reviews (review_id, tenant_id, data, status, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (review_id, tenant_id, json.dumps(review_data), "pending", review_data["created_at"])
                )
        return review_id

    def get_pending_reviews(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """Get all pending manual reviews for a tenant."""
        tenant_id = tenant_id or self.tenant_id
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM telegram_pending_reviews WHERE tenant_id = %s AND status = 'pending'",
                    (tenant_id,)
                )
                rows = cur.fetchall()
                return [json.loads(r["data"]) for r in rows]

    def resolve_review(self, review_id: str, admin_decision: str, admin_notes: str = "", tenant_id: str = None) -> bool:
        """Resolve a pending review with admin decision."""
        tenant_id = tenant_id or self.tenant_id
        self._ensure_tenant(tenant_id)
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM telegram_pending_reviews WHERE review_id = %s AND tenant_id = %s",
                    (review_id, tenant_id)
                )
                row = cur.fetchone()
                if not row:
                    return False
                
                review = json.loads(row["data"])
                review["status"] = "resolved"
                review["admin_decision"] = admin_decision
                review["admin_notes"] = admin_notes
                review["resolved_at"] = datetime.now(timezone.utc).isoformat()
                
                cur.execute(
                    "UPDATE telegram_pending_reviews SET data = %s, status = 'resolved' WHERE review_id = %s",
                    (json.dumps(review), review_id)
                )
        return True

    async def execute_review_decision(self, review_id: str, tenant_id: str = None):
        """Execute the admin decision for a review."""
        tenant_id = tenant_id or self.tenant_id
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM telegram_pending_reviews WHERE review_id = %s AND tenant_id = %s",
                    (review_id, tenant_id)
                )
                row = cur.fetchone()
        
        if not row:
            return {"status": "failed", "error": "Review not found"}
            
        review = json.loads(row["data"])
        
        if review.get("status") != "resolved":
            return {"status": "failed", "error": "Review not yet resolved by admin"}
            
        admin_decision = review.get("admin_decision")
        original_message = review.get("original_message", {})
        user_id = original_message.get("from", {}).get("id")
        chat_id = original_message.get("chat", {}).get("id")
        message_id = original_message.get("message_id")
        
        bot_token = self._bot_token_for_tenant(tenant_id)
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, cannot execute admin decision")
            return {
                "status": "failed",
                "review_id": review_id,
                "error": "Telegram bot token not configured"
            }
        
        # Execute the appropriate Telegram API action
        if admin_decision == "ban":
            # Ban user from chat
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            payload = {
                "chat_id": chat_id,
                "user_id": user_id
            }
            
        elif admin_decision == "kick":
            # Kick user from chat (ban for 1 minute)
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            payload = {
                "chat_id": chat_id,
                "user_id": user_id,
                "until_date": int(datetime.now(timezone.utc).timestamp()) + 60  # 1 minute from now
            }
            
        elif admin_decision == "warn":
            # Send warning message
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "⚠️ Warning: Your message violated group rules. Further violations may result in a ban.",
                "reply_to_message_id": message_id
            }
            
        elif admin_decision == "delete":
            # Delete the message
            url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id
            }
            
        else:  # allow or unknown
            return {
                "status": "skipped",
                "review_id": review_id,
                "action": admin_decision,
                "message": f"No action required for decision: {admin_decision}"
            }
        
        try:
            response = await self.http_client.post(url, json=payload)
            
            if response.status_code != 200:
                error_msg = f"Telegram API error: {response.text}"
                logger.error(error_msg)
                return {
                    "status": "failed",
                    "review_id": review_id,
                    "action": admin_decision,
                    "error": error_msg
                }
                
            logger.info(f"Successfully executed {admin_decision} for user {user_id} in chat {chat_id}")
            
            return {
                "status": "executed",
                "review_id": review_id,
                "action": admin_decision,
                "telegram_response": response.json(),
                "message": f"Admin decision {admin_decision} executed successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to execute {admin_decision}: {e}", exc_info=True)
            return {
                "status": "failed",
                "review_id": review_id,
                "action": admin_decision,
                "error": "admin_action_execution_failed",
            }

    async def _handle_manual_review(self, action: Dict[str, Any], update: Dict[str, Any], result: Dict[str, Any], tenant_id: str = None):
        """Handle cases that require manual admin review."""
        tenant_id = tenant_id or self.tenant_id
        
        try:
            # Create review data
            review_data = {
                "action": action,
                "update": update,
                "evaluation": result,
                "user_info": update.get("message", {}).get("from", {}),
                "chat_info": update.get("message", {}).get("chat", {}),
                "message_text": update.get("message", {}).get("text", ""),
                "threat_categories": result["final"].get("threat_categories", []),
                "risk_factors": result["final"].get("risk_factors", []),
                "original_message": update.get("message", {})
            }
            
            # Add to pending reviews (tenant-isolated)
            review_id = self.add_pending_review(review_data, tenant_id)
            
            # Notify all admin chats for this tenant
            notification_tasks = []
            for admin_chat_id in self.admin_chats.get(tenant_id, set()):
                notification_tasks.append(self._notify_admin(admin_chat_id, review_data, review_id, tenant_id))
                
            await asyncio.gather(*notification_tasks)
            
            logger.info(f"[{tenant_id}] Manual review created: {review_id}")
            
        except Exception as e:
            logger.error(f"[{tenant_id}] Failed to create manual review: {e}", exc_info=True)

    async def _notify_admin(self, admin_chat_id: int, review_data: Dict[str, Any], review_id: str, tenant_id: str = None):
        """Notify admin about a case requiring manual review."""
        tenant_id = tenant_id or self.tenant_id
        
        try:
            bot_token = self._bot_token_for_tenant(tenant_id)
            if not bot_token:
                logger.warning(f"[{tenant_id}] TELEGRAM_BOT_TOKEN not set, cannot send admin notifications")
                return
                
            user_info = review_data["user_info"]
            chat_info = review_data["chat_info"]
            
            base_url = os.environ.get("BASE_URL")
            review_link = f"\n👉 Review dashboard: {base_url}/reviews/{review_id}?tenant={tenant_id}" if base_url else ""
            
            notification_message = (
                f"🚨 [{tenant_id}] MANUAL REVIEW REQUIRED 🚨\n\n"
                f"📝 Review ID: {review_id}\n"
                f"🏢 Tenant: {tenant_id}\n"
                f"👤 User: {user_info.get('username', 'N/A')} (ID: {user_info.get('id', 'N/A')})\n"
                f"💬 Chat: {chat_info.get('title', 'Private')} (ID: {chat_info.get('id', 'N/A')})\n"
                f"📱 Message: {review_data['message_text'][:100]}...\n"
                f"⚠️  Threats: {', '.join(review_data['threat_categories'])}\n"
                f"🔍 Confidence: {review_data['action'].get('confidence', 0):.2f}"
                f"{review_link}"
            )
            
            # Send via Telegram Bot API
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": admin_chat_id,
                "text": notification_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            response = await self.http_client.post(url, json=payload)
            
            if response.status_code != 200:
                logger.error(f"[{tenant_id}] Failed to send Telegram notification: {response.text}")
            else:
                logger.info(f"[{tenant_id}] Admin notification sent to chat {admin_chat_id}")
                
        except Exception as e:
            logger.error(f"[{tenant_id}] Failed to notify admin {admin_chat_id}: {e}", exc_info=True)


# Initialize service
service = TelegramProtectionService()


# Exception handlers - CRITICAL: No silent failures
# Note: Exception handlers must be added to main app, not router

# Telegram Webhook Endpoint
@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receive Telegram webhook updates.

    This is the main entry point for Telegram bot updates.
    Set this as your webhook URL: https://your-server/telegram/webhook
    """
    try:
        body = await request.json()
        update = body
        
        # Extract tenant ID from the update (could be from chat ID, bot token, or custom field)
        # For now, we'll use a simple approach - you may want to customize this
        tenant_id = _tenant_id_from_request(request)
        _verify_webhook_secret(request, tenant_id)
        
        logger.info(f"[{tenant_id}] Received Telegram update: {update.get('update_id')}")
        
        # Use the module-level singleton — NOT a fresh instance per request
        action = await service.process_update(update, tenant_id=tenant_id)
        
        if not action:
            return {"ok": True, "action": "ignored"}
        
        # Return action for the bot to execute
        return {
            "ok": True,
            "action": action.get("action"),
            "reason": action.get("reason", ""),
            "confidence": action.get("confidence", 0),
            "details": action.get("evaluation", {}),
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Telegram webhook processing failed") from e


# Admin endpoints
@router.get("/status", dependencies=[Depends(require_telegram_admin)])
async def get_status(request: Request):
    """Get protection service status for a tenant."""
    tenant_id = _tenant_id_from_request(request)
    show_all = request.query_params.get("all", "false").lower() == "true"
    if show_all and tenant_id == "default":
        return service.get_status("all")
    else:
        return service.get_status(tenant_id)


@router.post("/groups/{group_id}/protect", dependencies=[Depends(require_telegram_admin)])
async def protect_group(group_id: int, request: Request, admin_chat_id: int = None):
    """Register a group for protection."""
    tenant_id = _tenant_id_from_request(request)
    service.register_group(group_id, admin_chat_id, tenant_id=tenant_id)
    return {"ok": True, "tenant_id": tenant_id, "group_id": group_id, "status": "protected"}


@router.get("/groups/{group_id}/members", dependencies=[Depends(require_telegram_admin)])
async def get_group_members(group_id: int):
    """Get member analysis for a group (for audit)."""
    # This would integrate with Telegram API to get all members
    return {
        "group_id": group_id,
        "message": "Member scan endpoint - requires Telegram API token configuration"
    }


@router.get("/reviews", dependencies=[Depends(require_telegram_admin)])
async def get_all_reviews(request: Request):
    """Get all pending manual reviews for a tenant."""
    tenant_id = _tenant_id_from_request(request)
    reviews = service.get_pending_reviews(tenant_id)
    return {"tenant_id": tenant_id, "pending_reviews": reviews, "count": len(reviews)}


@router.get("/reviews/{review_id}", dependencies=[Depends(require_telegram_admin)])
async def get_review_details(review_id: str, request: Request):
    """Get details of a specific manual review."""
    tenant_id = _tenant_id_from_request(request)
    reviews = service.get_pending_reviews(tenant_id)
    review = next((r for r in reviews if r["review_id"] == review_id), None)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("/reviews/{review_id}/resolve", dependencies=[Depends(require_telegram_admin)])
async def resolve_review(review_id: str, resolution: Dict[str, Any], request: Request):
    """Resolve a manual review with admin decision."""
    tenant_id = _tenant_id_from_request(request)
    
    admin_decision = resolution.get("decision")  # "allow", "ban", "kick", "warn"
    admin_notes = resolution.get("notes", "")
    
    if not admin_decision:
        raise HTTPException(status_code=400, detail="Decision is required")
        
    success = service.resolve_review(review_id, admin_decision, admin_notes, tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Review not found")
        
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "review_id": review_id,
        "admin_decision": admin_decision,
        "admin_notes": admin_notes
    }


@router.post("/reviews/{review_id}/execute", dependencies=[Depends(require_telegram_admin)])
async def execute_review_decision(review_id: str, request: Request):
    """Execute the admin decision for a review."""
    tenant_id = _tenant_id_from_request(request)
    
    reviews = service.get_pending_reviews(tenant_id)
    review = next((r for r in reviews if r["review_id"] == review_id), None)
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    if review.get("status") != "resolved":
        raise HTTPException(status_code=400, detail="Review not yet resolved by admin")
        
    result = await service.execute_review_decision(review_id, tenant_id)
    
    if result["status"] != "executed":
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to execute decision"))
        
    return {
        "status": "executed",
        "tenant_id": tenant_id,
        "review_id": review_id,
        "action": result["action"],
        "message": result["message"],
        "telegram_response": result.get("telegram_response")
    }


@router.get("/config", dependencies=[Depends(require_telegram_admin)])
async def get_tenant_config(request: Request):
    """Get current tenant configuration."""
    tenant_id = _tenant_id_from_request(request)
    service._ensure_tenant(tenant_id)
    
    return {
        "tenant_id": tenant_id,
        "tenant_name": os.environ.get(f"TENANT_NAME_{tenant_id.upper()}", tenant_id),
        "configuration": service.tenant_configs[tenant_id],
        "active_detectors": list(service.tenant_adapters[tenant_id].active_detectors.keys())
    }


@router.post("/config/detectors", dependencies=[Depends(require_telegram_admin)])
async def configure_detectors(request: Request, config: Dict[str, Any]):
    """Configure detectors for a tenant (admin only)."""
    tenant_id = _tenant_id_from_request(request)
    
    # Validate configuration
    if not config or 'detectors' not in config:
        raise HTTPException(status_code=400, detail="Configuration must include 'detectors' section")
    
    updated = service.update_tenant_config(tenant_id, config)
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "message": "Configuration updated for this running service instance",
        "configuration": updated,
        "active_detectors": list(service.tenant_adapters[tenant_id].active_detectors.keys()),
    }


@router.get("/config/options", dependencies=[Depends(require_telegram_admin)])
async def get_configuration_options():
    """Get available configuration options."""
    return {
        "detectors": {
            "core": ["child_exploitation", "illegal_content"],
            "policy": ["copyright_violation", "torrent_sharing", "crypto_mining", "remote_access"],
            "custom": "Available for enterprise clients"
        },
        "configuration_rules": {
            "core_detectors": "Always enabled, non-configurable for security",
            "policy_detectors": "Can be enabled/disabled, patterns can be extended",
            "custom_detectors": "Enterprise feature - contact support",
            "thresholds": "Adjustable confidence levels for actions"
        },
        "examples": {
            "disable_copyright": {
                "detectors": {
                    "copyright_violation": {
                        "enabled": False
                    }
                }
            },
            "add_custom_patterns": {
                "detectors": {
                    "torrent_sharing": {
                        "enabled": True,
                        "patterns": ["additional.*pattern.*here"]
                    }
                }
            },
            "adjust_thresholds": {
                "response_thresholds": {
                    "ban": 0.9,
                    "kick": 0.7,
                    "review": 0.5
                }
            }
        }
    }


@router.post("/groups/{group_id}/audit", dependencies=[Depends(require_telegram_admin)])
async def run_audit(group_id: int, request: Request):
    """
    Run a full audit of group members.
    
    Scans all members and identifies bots.
    """
    # Placeholder - would implement full audit logic
    return {
        "tenant_id": _tenant_id_from_request(request),
        "group_id": group_id,
        "status": "audit_queued",
        "estimated_time": "5 minutes"
    }


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "TelegramProtection",
        "truepresence_version": "1.0.0"
    }


# Run locally for testing
if __name__ == "__main__":
    import uvicorn

    from truepresence.main import app

    port = int(os.environ.get("PORT", "8000"))
    
    logger.info(f"Starting TruePresence Telegram Protection on port {port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
