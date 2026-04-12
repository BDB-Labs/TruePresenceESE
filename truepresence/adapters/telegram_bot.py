"""
Telegram Bot Server for TruePresence

Webhook server that receives Telegram updates and processes them through
TruePresence for bot detection and group protection.

CRITICAL: This system does NOT fail silently.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio

# Configure logging - CRITICAL systems must log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TruePresence Telegram Protection", version="1.0.0")

# Import TruePresence components
from truepresence.core.orchestrator import TruePresenceOrchestrator
from truepresence.adapters.telegram import TelegramAdapter
from truepresence.exceptions import TruePresenceError, OrchestratorError


class TelegramProtectionService:
    """
    Main service for Telegram group protection.
    
    Coordinates Telegram webhook events with TruePresence evaluation.
    """
    
    def __init__(self):
        logger.info("Initializing TelegramProtectionService")
        
        self.orchestrator = TruePresenceOrchestrator()
        self.adapter = TelegramAdapter()
        self.admin_chats = set()
        self.protected_groups = set()
        
        # Per-user session memories
        self.user_sessions: Dict[str, Any] = {}
        
        logger.info("TelegramProtectionService initialized")
    
    async def process_update(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a Telegram update through TruePresence.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Action to take or None
        """
        try:
            # Parse into TruePresence event
            event = self.adapter.parse_update(update)
            
            if not event:
                logger.debug("No relevant event to process")
                return None
            
            logger.info(f"Processing {event['event_type']} from user {event['context'].get('user_id')}")
            
            # Get or create session for this user
            user_id = event["context"].get("user_id", "unknown")
            session_id = f"tg_{user_id}"
            
            if session_id not in self.user_sessions:
                self.user_sessions[session_id] = {"session_id": session_id}
            
            session = self.user_sessions[session_id]
            
            # Evaluate with TruePresence
            result = self.orchestrator.evaluate(session, event)
            
            # Convert to Telegram action
            action = self.adapter.build_response(result["final"])
            
            logger.info(f"Decision: {action['action']} (confidence: {action.get('confidence', 0):.2f})")
            
            # Add full result context for debugging
            action["evaluation"] = {
                "human_probability": result["final"].get("human_probability"),
                "risk_factors": result["final"].get("risk_factors", []),
                "disagreement": result["final"].get("disagreement", 0)
            }
            
            return action
            
        except TruePresenceError as e:
            logger.error(f"TruePresence error: {e.message}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"UNHANDLED ERROR: {e}", exc_info=True)
            raise
    
    def register_group(self, group_id: int, admin_chat_id: int = None):
        """Register a group for protection."""
        self.protected_groups.add(group_id)
        if admin_chat_id:
            self.admin_chats.add(admin_chat_id)
        logger.info(f"Registered group {group_id} for protection")
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "status": "healthy",
            "protected_groups": len(self.protected_groups),
            "active_sessions": len(self.user_sessions),
            "orchestrator_health": self.orchestrator.health_check()
        }


# Initialize service
service = TelegramProtectionService()


# Exception handlers - CRITICAL: No silent failures
@app.exception_handler(TruePresenceError)
async def tp_exception_handler(request: Request, exc: TruePresenceError):
    logger.error(f"TruePresence error: {exc.message}")
    return JSONResponse(
        status_code=500,
        content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.critical(f"UNHANDLED: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "InternalError", "message": str(exc)}
    )


# Telegram Webhook Endpoint
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receive Telegram webhook updates.
    
    This is the main entry point for Telegram bot updates.
    Set this as your webhook URL: https://your-server/webhook
    """
    try:
        body = await request.json()
        update = body
        
        logger.info(f"Received Telegram update: {update.get('update_id')}")
        
        # Process through TruePresence
        action = await service.process_update(update)
        
        if not action:
            return {"ok": True, "action": "ignored"}
        
        # Return action for the bot to execute
        return {
            "ok": True,
            "action": action.get("action"),
            "reason": action.get("reason", ""),
            "confidence": action.get("confidence", 0),
            "details": action.get("evaluation", {})
        }
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Admin endpoints
@app.get("/status")
async def get_status():
    """Get protection service status."""
    return service.get_status()


@app.post("/groups/{group_id}/protect")
async def protect_group(group_id: int, admin_chat_id: int = None):
    """Register a group for protection."""
    service.register_group(group_id, admin_chat_id)
    return {"ok": True, "group_id": group_id, "status": "protected"}


@app.get("/groups/{group_id}/members")
async def get_group_members(group_id: int):
    """Get member analysis for a group (for audit)."""
    # This would integrate with Telegram API to get all members
    return {
        "group_id": group_id,
        "message": "Member scan endpoint - requires Telegram API token configuration"
    }


@app.post("/groups/{group_id}/audit")
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
@app.get("/health")
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