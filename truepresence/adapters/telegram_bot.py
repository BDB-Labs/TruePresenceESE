"""
Telegram Bot Server for TruePresence

Webhook server that receives Telegram updates and processes them through
TruePresence for bot detection and group protection.

CRITICAL: This system does NOT fail silently.
"""

import os
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import httpx

# Configure logging - CRITICAL systems must log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use router instead of separate app
router = APIRouter(prefix="/telegram", tags=["telegram"])

# Import TruePresence components
from truepresence.core.orchestrator_v3 import TruePresenceOrchestratorV3 as TruePresenceOrchestratorV3
from truepresence.adapters.telegram import TelegramAdapter
from truepresence.exceptions import TruePresenceError, OrchestratorError


class TelegramProtectionService:
    """
    Main service for Telegram group protection.

    Coordinates Telegram webhook events with TruePresence evaluation.
    Now supports multi-tenancy for different client instances.
    """

    def __init__(self, tenant_id: str = "default"):
        logger.info(f"Initializing TelegramProtectionService for tenant: {tenant_id}")

        self.tenant_id = tenant_id
        self.orchestrator = TruePresenceOrchestratorV3()
        
        # Load tenant-specific configuration
        self.tenant_config = self._load_tenant_config(tenant_id)
        self.adapter = TelegramAdapter(self.tenant_config)
        
        # Multi-tenant data structures
        self.admin_chats: Dict[str, set] = {tenant_id: set()}
        self.protected_groups: Dict[str, set] = {tenant_id: set()}
        self.user_sessions: Dict[str, Dict[str, Any]] = {tenant_id: {}}
        self.pending_reviews: Dict[str, Dict[str, Dict[str, Any]]] = {tenant_id: {}}
        
        # Tenant-specific configuration
        self.bot_token = os.environ.get(f"TELEGRAM_BOT_TOKEN_{tenant_id.upper()}") or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.http_client = httpx.AsyncClient()
        
        # Tenant metadata
        self.tenant_name = os.environ.get(f"TENANT_NAME_{tenant_id.upper()}", tenant_id)
        self.tenant_created = datetime.now(timezone.utc).isoformat()

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
    
    async def process_update(self, update: Dict[str, Any], tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Process a Telegram update through TruePresence.

        Args:
            update: Raw Telegram webhook update
            tenant_id: Tenant identifier for multi-tenancy support

        Returns:
            Action to take or None
        """
        tenant_id = tenant_id or self.tenant_id
        
        # Initialize tenant if not exists
        if tenant_id not in self.user_sessions:
            self.user_sessions[tenant_id] = {}
            self.pending_reviews[tenant_id] = {}
        
        try:
            # Parse into TruePresence event
            event = self.adapter.parse_update(update)
            
            if not event:
                logger.debug(f"[{tenant_id}] No relevant event to process")
                return None
            
            logger.info(f"[{tenant_id}] Processing {event['event_type']} from user {event['context'].get('user_id')}")
            
            # Get or create session for this user (tenant-isolated)
            user_id = event["context"].get("user_id", "unknown")
            session_id = f"tg_{tenant_id}_{user_id}"
            
            if session_id not in self.user_sessions[tenant_id]:
                self.user_sessions[tenant_id][session_id] = {"session_id": session_id, "tenant_id": tenant_id}
            
            session = self.user_sessions[tenant_id][session_id]
            
            # Evaluate with TruePresence
            result = self.orchestrator.evaluate(session, event)
            
            # Pull threat_categories from adversarial role output and inject into final
            adversarial_output = result.get("roles", {}).get("adversarial", {})
            threat_categories = adversarial_output.get("threat_categories", [])
            block_reason = adversarial_output.get("block_reason", "")
            result["final"]["threat_categories"] = threat_categories
            result["final"]["block_reason"] = block_reason
            
            # Convert to Telegram action
            action = self.adapter.build_response(result["final"])
            
            logger.info(f"[{tenant_id}] Decision: {action['action']} (confidence: {action.get('confidence', 0):.2f})")
            
            # Add full result context for debugging
            action["evaluation"] = {
                "human_probability": result["final"].get("human_probability"),
                "risk_factors": result["final"].get("risk_factors", []),
                "disagreement": result["final"].get("disagreement", 0)
            }
            
            # Handle manual review cases
            if action.get("action") == "alert_admin":
                await self._handle_manual_review(action, update, result, tenant_id)
            
            return action
            
        except TruePresenceError as e:
            logger.error(f"[{tenant_id}] TruePresence error: {e.message}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"[{tenant_id}] UNHANDLED ERROR: {e}", exc_info=True)
            raise
    
    def register_group(self, group_id: int, admin_chat_id: int = None, tenant_id: str = None):
        """Register a group for protection."""
        tenant_id = tenant_id or self.tenant_id
        
        # Initialize tenant if not exists
        if tenant_id not in self.protected_groups:
            self.protected_groups[tenant_id] = set()
            self.admin_chats[tenant_id] = set()
            self.user_sessions[tenant_id] = {}
            self.pending_reviews[tenant_id] = {}
        
        self.protected_groups[tenant_id].add(group_id)
        if admin_chat_id:
            self.admin_chats[tenant_id].add(admin_chat_id)
        logger.info(f"[{tenant_id}] Registered group {group_id} for protection")
    
    def get_status(self, tenant_id: str = None) -> Dict[str, Any]:
        """Get service status for a tenant or all tenants."""
        tenant_id = tenant_id or self.tenant_id
        
        if tenant_id == "all":
            # Return status for all tenants
            tenant_statuses = {}
            for tid in self.user_sessions.keys():
                tenant_statuses[tid] = {
                    "protected_groups": len(self.protected_groups.get(tid, set())),
                    "active_sessions": len(self.user_sessions.get(tid, {})),
                    "pending_reviews": len(self.pending_reviews.get(tid, {})),
                    "orchestrator_health": self.orchestrator.health_check()
                }
            
            return {
                "status": "healthy",
                "multi_tenant": True,
                "tenants": tenant_statuses,
                "total_tenants": len(tenant_statuses)
            }
        else:
            # Return status for specific tenant
            return {
                "status": "healthy",
                "tenant_id": tenant_id,
                "protected_groups": len(self.protected_groups.get(tenant_id, set())),
                "active_sessions": len(self.user_sessions.get(tenant_id, {})),
                "pending_reviews": len(self.pending_reviews.get(tenant_id, {})),
                "orchestrator_health": self.orchestrator.health_check()
            }

    def add_pending_review(self, review_data: Dict[str, Any], tenant_id: str = None):
        """Add a case that requires manual review."""
        tenant_id = tenant_id or self.tenant_id
        
        # Initialize tenant if not exists
        if tenant_id not in self.pending_reviews:
            self.pending_reviews[tenant_id] = {}
        
        review_id = str(uuid.uuid4())
        review_data["review_id"] = review_id
        review_data["status"] = "pending"
        review_data["created_at"] = datetime.now(timezone.utc).isoformat()
        review_data["tenant_id"] = tenant_id
        
        self.pending_reviews[tenant_id][review_id] = review_data
        return review_id

    def get_pending_reviews(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """Get all pending manual reviews for a tenant."""
        tenant_id = tenant_id or self.tenant_id
        return list(self.pending_reviews.get(tenant_id, {}).values())

    def resolve_review(self, review_id: str, admin_decision: str, admin_notes: str = "", tenant_id: str = None) -> bool:
        """Resolve a pending review with admin decision."""
        tenant_id = tenant_id or self.tenant_id
        
        if tenant_id not in self.pending_reviews or review_id not in self.pending_reviews[tenant_id]:
            return False
            
        review = self.pending_reviews[tenant_id][review_id]
        review["status"] = "resolved"
        review["admin_decision"] = admin_decision
        review["admin_notes"] = admin_notes
        review["resolved_at"] = datetime.now(timezone.utc).isoformat()
        
        return True

    async def execute_review_decision(self, review_id: str, tenant_id: str = None):
        """Execute the admin decision for a review."""
        tenant_id = tenant_id or self.tenant_id
        tenant_reviews = self.pending_reviews.get(tenant_id, {})
        
        if review_id not in tenant_reviews:
            return {"status": "failed", "error": "Review not found"}
            
        review = tenant_reviews[review_id]
        
        if review.get("status") != "resolved":
            return {"status": "failed", "error": "Review not yet resolved by admin"}
            
        admin_decision = review.get("admin_decision")
        original_message = review.get("original_message", {})
        user_id = original_message.get("from", {}).get("id")
        chat_id = original_message.get("chat", {}).get("id")
        message_id = original_message.get("message_id")
        
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, cannot execute admin decision")
            return {
                "status": "failed",
                "review_id": review_id,
                "error": "Telegram bot token not configured"
            }
        
        # Execute the appropriate Telegram API action
        if admin_decision == "ban":
            # Ban user from chat
            url = f"https://api.telegram.org/bot{self.bot_token}/banChatMember"
            payload = {
                "chat_id": chat_id,
                "user_id": user_id
            }
            
        elif admin_decision == "kick":
            # Kick user from chat (ban for 1 minute)
            url = f"https://api.telegram.org/bot{self.bot_token}/banChatMember"
            payload = {
                "chat_id": chat_id,
                "user_id": user_id,
                "until_date": int(datetime.now(timezone.utc).timestamp()) + 60  # 1 minute from now
            }
            
        elif admin_decision == "warn":
            # Send warning message
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": f"⚠️ Warning: Your message violated group rules. Further violations may result in a ban.",
                "reply_to_message_id": message_id
            }
            
        elif admin_decision == "delete":
            # Delete the message
            url = f"https://api.telegram.org/bot{self.bot_token}/deleteMessage"
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
                "error": str(e)
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
            bot_token = os.environ.get(f"TELEGRAM_BOT_TOKEN_{tenant_id.upper()}") or os.environ.get("TELEGRAM_BOT_TOKEN")
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
    Set this as your webhook URL: https://your-server/webhook
    """
    try:
        body = await request.json()
        update = body
        
        # Extract tenant ID from the update (could be from chat ID, bot token, or custom field)
        # For now, we'll use a simple approach - you may want to customize this
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        
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
        raise HTTPException(status_code=500, detail=str(e))


# Admin endpoints
@router.get("/status")
async def get_status(request: Request):
    """Get protection service status for a tenant."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    show_all = request.query_params.get("all", "false").lower() == "true"
    if show_all and tenant_id == "default":
        return service.get_status("all")
    else:
        return service.get_status(tenant_id)


@router.post("/groups/{group_id}/protect")
async def protect_group(group_id: int, admin_chat_id: int = None):
    """Register a group for protection."""
    service.register_group(group_id, admin_chat_id)
    return {"ok": True, "group_id": group_id, "status": "protected"}


@router.get("/groups/{group_id}/members")
async def get_group_members(group_id: int):
    """Get member analysis for a group (for audit)."""
    # This would integrate with Telegram API to get all members
    return {
        "group_id": group_id,
        "message": "Member scan endpoint - requires Telegram API token configuration"
    }


@router.get("/reviews")
async def get_all_reviews(request: Request):
    """Get all pending manual reviews for a tenant."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    reviews = service.get_pending_reviews(tenant_id)
    return {"tenant_id": tenant_id, "pending_reviews": reviews, "count": len(reviews)}


@router.get("/reviews/{review_id}")
async def get_review_details(review_id: str, request: Request):
    """Get details of a specific manual review."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    reviews = service.get_pending_reviews(tenant_id)
    review = next((r for r in reviews if r["review_id"] == review_id), None)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("/reviews/{review_id}/resolve")
async def resolve_review(review_id: str, resolution: Dict[str, Any], request: Request):
    """Resolve a manual review with admin decision."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    tenant_service = TelegramProtectionService(tenant_id=tenant_id)
    
    admin_decision = resolution.get("decision")  # "allow", "ban", "kick", "warn"
    admin_notes = resolution.get("notes", "")
    
    if not admin_decision:
        raise HTTPException(status_code=400, detail="Decision is required")
        
    success = tenant_service.resolve_review(review_id, admin_decision, admin_notes, tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Review not found")
        
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "review_id": review_id,
        "admin_decision": admin_decision,
        "admin_notes": admin_notes
    }


@router.post("/reviews/{review_id}/execute")
async def execute_review_decision(review_id: str, request: Request):
    """Execute the admin decision for a review."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    tenant_service = TelegramProtectionService(tenant_id=tenant_id)
    
    reviews = tenant_service.get_pending_reviews(tenant_id)
    review = next((r for r in reviews if r["review_id"] == review_id), None)
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    if review.get("status") != "resolved":
        raise HTTPException(status_code=400, detail="Review not yet resolved by admin")
        
    result = await tenant_service.execute_review_decision(review_id)
    
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


@router.get("/config")
async def get_tenant_config(request: Request):
    """Get current tenant configuration."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    tenant_service = TelegramProtectionService(tenant_id=tenant_id)
    
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_service.tenant_name,
        "configuration": tenant_service.tenant_config,
        "active_detectors": list(tenant_service.adapter.active_detectors.keys())
    }


@router.post("/config/detectors")
async def configure_detectors(request: Request, config: Dict[str, Any]):
    """Configure detectors for a tenant (admin only)."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    
    # In production, add admin authentication here
    # if not is_admin(request):
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate configuration
    if not config or 'detectors' not in config:
        raise HTTPException(status_code=400, detail="Configuration must include 'detectors' section")
    
    # Store configuration (in production, use database)
    # For now, we'll return what would be saved
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "message": "Configuration would be saved to database",
        "configuration": config
    }


@router.get("/config/options")
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


@router.post("/groups/{group_id}/audit")
async def run_audit(group_id: int):
    """
    Run a full audit of group members.
    
    Scans all members and identifies bots.
    """
    # Placeholder - would implement full audit logic
    return {
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
    
    port = int(os.environ.get("PORT", "8000"))
    
    logger.info(f"Starting TruePresence Telegram Protection on port {port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)