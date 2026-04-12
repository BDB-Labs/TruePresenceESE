"""
Telegram Adapter for TruePresence

Converts Telegram webhook events into TruePresence evaluation events.
Includes detection for: Mirrors/Userbots, Crypto Miners, DMCA, Torrents, VNC, Illegal Content
"""

import re
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """
    Adapts Telegram events to TruePresence events.
    
    Maps Telegram's update types to TruePresence's evaluation format.
    Detects specific threat categories.
    """
    
    # Known patterns for threat detection
    TORRENT_PATTERNS = [
        r'magnet:\?xt=urn:btih:',
        r'\.torrent$',
        r'torrentz2',
        r'kickasstorrents',
        r'rarbg',
        r'yts\.movies',
        r'1337x',
        r'thepiratebay',
        r'tpb\.',
    ]
    
    CRYPTO_MINING_PATTERNS = [
        r'monero',
        r'xmrig',
        r'cryptonight',
        r'nicehash',
        r'pool\.mine',
        r'stratum\+tcp',
    ]
    
    VNC_PATTERNS = [
        r'vnc://',
        r'rdp://',
        r'remote\.desktop',
        r'anydesk',
        r'teamviewer',
    ]
    
    COPYRIGHT_PATTERNS = [
        r'download.*full.*movie',
        r'free.*download',
        r'full.*album',
        r'leaked.*album',
        r'pirated',
    ]
    
    ILLEGAL_PATTERNS = [
        r'buy.*drugs',
        r'fake.*id',
        r'carding',
        r'hacking.*service',
        r'weapon.*sale',
    ]
    
    def __init__(self):
        self.user_sessions = {}  # user_id -> session data
        # Compile patterns for efficiency
        self._torrent_re = re.compile('|'.join(self.TORRENT_PATTERNS), re.I)
        self._crypto_re = re.compile('|'.join(self.CRYPTO_MINING_PATTERNS), re.I)
        self._vnc_re = re.compile('|'.join(self.VNC_PATTERNS), re.I)
        self._copyright_re = re.compile('|'.join(self.COPYRIGHT_PATTERNS), re.I)
        self._illegal_re = re.compile('|'.join(self.ILLEGAL_PATTERNS), re.I)
        
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
        """Parse a message event with threat detection."""
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        text = message.get("text", "") or ""
        
        # Analyze content for threats
        threat_analysis = self._analyze_content(text)
        
        return {
            "event_type": "message",
            "timestamp": message.get("date", 0),
            "payload": {
                "message_id": message.get("message_id"),
                "text": text,
                "has_attachments": bool(message.get("photo") or message.get("video") or message.get("document")),
                "is_reply": message.get("reply_to_message") is not None,
                "chat_type": chat.get("type"),
            },
            "features": {
                "text_length": len(text),
                # Threat indicators
                "torrent_indicators": threat_analysis["torrent_score"],
                "crypto_mining_indicators": threat_analysis["crypto_score"],
                "vnc_indicators": threat_analysis["vnc_score"],
                "copyright_indicators": threat_analysis["copyright_score"],
                "illegal_indicators": threat_analysis["illegal_keywords"],
                "mirrored_content_score": threat_analysis["mirrored_score"],
                # Behavioral signals
                "message_velocity": 0,  # Calculated in bot
                "content_similarity": 0,  # Calculated over time
            },
            "context": {
                "platform": "telegram",
                "user_id": from_user.get("id"),
                "username": from_user.get("username", ""),
                "is_bot": from_user.get("is_bot", False),
                "group_id": chat.get("id"),
            },
            "threat_analysis": threat_analysis
        }
    
    def _analyze_content(self, text: str) -> Dict[str, Any]:
        """Analyze message content for specific threat categories."""
        text_lower = text.lower()
        
        # Check each category
        torrent_matches = self._torrent_re.findall(text_lower)
        crypto_matches = self._crypto_re.findall(text_lower)
        vnc_matches = self._vnc_re.findall(text_lower)
        copyright_matches = self._copyright_re.findall(text_lower)
        illegal_matches = self._illegal_re.findall(text_lower)
        
        # Calculate scores (0-1)
        torrent_score = min(1.0, len(torrent_matches) * 0.5)
        crypto_score = min(1.0, len(crypto_matches) * 0.5)
        vnc_score = min(1.0, len(vnc_matches) * 0.5)
        copyright_score = min(1.0, len(copyright_matches) * 0.5)
        
        # Illegal keywords
        illegal_keywords = illegal_matches
        
        # Mirror detection (simplified - would need cross-group analysis)
        mirrored_score = 0.0
        if len(text) > 100 and any(word in text_lower for word in ["join", "channel", "subscribe", "follow"]):
            mirrored_score = 0.7
        
        return {
            "torrent_score": torrent_score,
            "crypto_score": crypto_score,
            "vnc_score": vnc_score,
            "copyright_score": copyright_score,
            "illegal_keywords": illegal_keywords,
            "mirrored_score": mirrored_score,
            "threats_detected": [
                "torrents" if torrent_score > 0.5 else None,
                "crypto_miners" if crypto_score > 0.5 else None,
                "vnc_virtual_desktops" if vnc_score > 0.3 else None,
                "dmca_violations" if copyright_score > 0.5 else None,
                "illegal_content" if illegal_keywords else None,
                "mirrors_userbots" if mirrored_score > 0.6 else None,
            ]
        }
    
    def _parse_chat_member(self, chat_member: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a chat member update (join/leave) with threat detection."""
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
                # New member threat scores default to low
                "torrent_indicators": 0.0,
                "crypto_mining_indicators": 0.0,
                "vnc_indicators": 0.0,
                "copyright_indicators": 0.0,
                "illegal_indicators": [],
                "mirrored_content_score": 0.0,
            },
            "context": {
                "platform": "telegram",
                "user_id": user.get("id"),
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
                "is_bot": user.get("is_bot", False),
                "group_id": chat.get("id"),
                "group_title": chat.get("title", "")
            },
            "threat_analysis": {
                "threats_detected": []
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
        
        # Get threat categories if available
        threat_categories = evaluation_result.get("threat_categories", [])
        block_reason = evaluation_result.get("block_reason", "")
        
        # More aggressive blocking for confirmed threats
        if threat_categories:
            # Any confirmed threat category = immediate block
            if confidence > 0.6:
                return {
                    "action": "ban",
                    "reason": block_reason or f"Threat detected: {', '.join(threat_categories)}",
                    "confidence": confidence,
                    "threat_categories": threat_categories
                }
        
        if decision == "block" and confidence > 0.8:
            return {
                "action": "ban",
                "reason": block_reason or f"Bot detected ({human_prob:.0%} human probability)",
                "confidence": confidence
            }
        elif decision == "block" and confidence > 0.6:
            return {
                "action": "kick",
                "reason": block_reason or f"Suspicious ({human_prob:.0%} human probability)",
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