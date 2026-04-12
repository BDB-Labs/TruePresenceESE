"""
Telegram Adapter for TruePresence

Converts Telegram webhook events into TruePresence evaluation events.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """
    Adapts Telegram events to TruePresence events.
    
    Maps Telegram's update types to TruePresence's evaluation format.
    """
    
    def __init__(self):
        self.user_sessions = {}  # user_id -> session data
        
    def parse_update(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Telegram update into TruePresence event.
        
        Args:
            update: Telegram webhook update dictionary
            
        Returns:
            TruePresence-ready event or None if not relevant
        """
        try:
            # Handle different update types
            if "message" in update:
                return self._parse_message(update["message"])
            elif "edited_message" in update:
                return self._parse_message(update["edited_message"])
            elif "chat_member" in update:
                return self._parse_chat_member(update["chat_member"])
            elif "my_chat_member" in update:
                return self._parse_chat_member(update["my_chat_member"])
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse Telegram update: {e}", exc_info=True)
            return None
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a message event."""
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        
        return {
            "event_type": "message",
            "timestamp": message.get("date", 0),
            "payload": {
                "message_id": message.get("message_id"),
                "text": message.get("text", ""),
                "has_attachments": bool(message.get("photo") or message.get("video") or message.get("document")),
                "is_reply": message.get("reply_to_message") is not None,
                "chat_type": chat.get("type"),
            },
            "features": {
                "text_length": len(message.get("text", "")),
            },
            "context": {
                "platform": "telegram",
                "user_id": from_user.get("id"),
                "username": from_user.get("username", ""),
                "is_bot": from_user.get("is_bot", False),
                "group_id": chat.get("id"),
            }
        }
    
    def _parse_chat_member(self, chat_member: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a chat member update (join/leave)."""
        user = chat_member.get("user", {})
        chat = chat_member.get("chat", {})
        new_status = chat_member.get("new_chat_member", {}).get("status", "")
        
        event_type = {
            "member": "member_join",
            "left_member": "member_leave",
            "kicked": "member_banned",
            "restricted": "member_restricted",
        }.get(new_status, "member_update")
        
        return {
            "event_type": event_type,
            "timestamp": chat_member.get("date", 0),
            "payload": {
                "old_status": chat_member.get("old_chat_member", {}).get("status", ""),
                "new_status": new_status,
            },
            "features": {
                "account_age_days": self._estimate_account_age(user),
                "username_entropy": self._calc_entropy(user.get("username", "")),
                "previous_warnings": self._get_warning_count(user.get("id")),
            },
            "context": {
                "platform": "telegram",
                "user_id": user.get("id"),
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
                "is_bot": user.get("is_bot", False),
                "group_id": chat.get("id"),
                "group_title": chat.get("title", ""),
            }
        }
    
    def _estimate_account_age(self, user: Dict[str, Any]) -> int:
        """Estimate account age in days. Telegram API doesn't provide this directly."""
        # This would need to be enhanced with actual API calls
        # For now, return a default
        return 30  # Assume 30 days if unknown
    
    def _calc_entropy(self, text: str) -> float:
        """Calculate username entropy for bot detection."""
        import math
        if not text:
            return 0.0
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        entropy = -sum(f/len(text) * math.log2(f/len(text)) for f in freq.values() if f > 0)
        return round(entropy, 2)
    
    def _get_warning_count(self, user_id: int) -> int:
        """Get number of previous warnings for this user."""
        # Would query database in production
        return 0
    
    def build_response(self, evaluation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert TruePresence result to Telegram action.
        
        Args:
            evaluation_result: Result from orchestrator.evaluate()
            
        Returns:
            Action dictionary for Telegram bot to execute
        """
        decision = evaluation_result.get("decision", "allow")
        confidence = evaluation_result.get("confidence", 0.0)
        human_prob = evaluation_result.get("human_probability", 0.5)
        
        if decision == "block" and confidence > 0.8:
            return {
                "action": "ban",
                "reason": f"Bot detected ({human_prob:.0%} human probability)",
                "confidence": confidence
            }
        elif decision == "block" and confidence > 0.6:
            return {
                "action": "kick",
                "reason": f"Suspicious ({human_prob:.0%} human probability)",
                "confidence": confidence
            }
        elif decision == "challenge":
            return {
                "action": "challenge",
                "reason": "Verification required",
                "confidence": confidence
            }
        elif decision == "review":
            return {
                "action": "alert_admin",
                "reason": f"Review needed - {evaluation_result.get('risk_factors', [])}",
                "confidence": confidence
            }
        
        return {
            "action": "allow",
            "confidence": confidence
        }