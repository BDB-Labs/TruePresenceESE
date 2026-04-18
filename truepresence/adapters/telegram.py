"""
Telegram Adapter for TruePresence

Converts Telegram webhook events into TruePresence evaluation events.
Includes detection for: Mirrors/Userbots, Crypto Miners, DMCA, Torrents, VNC, Illegal Content
"""

import logging
import math
import re
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional

from truepresence.db import get_db
from truepresence.exceptions import EvidenceError

logger = logging.getLogger(__name__)

# Rate limiting for ban actions
_ban_actions: Dict[str, float] = {}  # user_id -> timestamp
BAN_COOLDOWN_SECONDS = 60  # Minimum seconds between ban actions per user


class TelegramAdapter:
    """
    Adapts Telegram events to TruePresence events.

    Maps Telegram's update types to TruePresence's evaluation format.
    Detects specific threat categories with configurable rules per tenant.
    """

    # Detection categories with tiered configuration
    # TIER 1: Core security (always enabled, non-configurable)
    CORE_DETECTORS = {
        'child_exploitation': {
            'enabled': True,  # Always enabled
            'configurable': False,
            'patterns': [
                r'\bchild.*porn\b',
                r'\bkiddie.*porn\b',
                r'\bcp\b(?!\s*(?:certificate|panel|apache|copyright))',
                r'\blolita\b(?!\s*(?:book|novel|nabokov))',
                r'\bpedo\b(?!\s*(?:bear|file|meter))',
            ]
        },
        'illegal_content': {
            'enabled': True,  # Always enabled
            'configurable': False,
            'patterns': [
                r'buy.*drugs',
                r'fake.*id', 
                r'carding',
                r'hacking.*service',
                r'weapon.*sale',
            ]
        }
    }

    # TIER 2: Business policy (configurable per tenant)
    POLICY_DETECTORS = {
        'copyright_violation': {
            'enabled': True,  # Default enabled
            'configurable': True,
            'patterns': [
                r'download.*full.*movie',
                r'free.*download',
                r'full.*album',
                r'leaked.*album',
                r'pirated',
            ]
        },
        'torrent_sharing': {
            'enabled': True,  # Default enabled
            'configurable': True,
            'patterns': [
                r'magnet:\?xt=urn:btih:',
                r'\.torrent$',
                r'torrentz2',
                r'kickasstorrents',
                r'rarbg',
            ]
        },
        'crypto_mining': {
            'enabled': True,  # Default enabled
            'configurable': True,
            'patterns': [
                r'monero',
                r'xmrig',
                r'cryptonight',
                r'nicehash',
                r'pool\.mine',
            ]
        },
        'remote_access': {
            'enabled': True,  # Default enabled
            'configurable': True,
            'patterns': [
                r'vnc://',
                r'rdp://',
                r'remote\.desktop',
                r'anydesk',
                r'teamviewer',
            ]
        }
    }

    # TIER 3: Custom detectors (available for enterprise clients)
    CUSTOM_DETECTORS = {}

    def __init__(self, tenant_config: Dict[str, Any] = None):
        self.tenant_config = tenant_config or {}

        # Per-user message timestamps for velocity calculation (last 60 seconds)
        # user_id -> deque of unix timestamps
        self._user_message_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Per-user recent message texts for similarity calculation
        # user_id -> deque of recent message texts
        self._user_recent_texts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))

        # Apply tenant-specific configuration
        self._configure_detectors()

        # Compile all enabled patterns
        self._compile_patterns()

    def _configure_detectors(self):
        """Apply tenant-specific detector configuration."""
        # Start with defaults
        self.active_detectors = {}
        
        # Always enable core detectors (non-configurable)
        for name, config in self.CORE_DETECTORS.items():
            self.active_detectors[name] = {
                'enabled': True,
                'patterns': config['patterns'],
                'tier': 'core'
            }
        
        # Apply policy detectors with tenant overrides
        for name, config in self.POLICY_DETECTORS.items():
            tenant_override = self.tenant_config.get('detectors', {}).get(name, {})
            
            enabled = tenant_override.get('enabled', config['enabled'])
            custom_patterns = tenant_override.get('patterns', [])
            
            patterns = config['patterns'] + custom_patterns
            
            self.active_detectors[name] = {
                'enabled': enabled,
                'patterns': patterns,
                'tier': 'policy'
            }
        
        # Add custom detectors if configured
        for name, config in self.tenant_config.get('custom_detectors', {}).items():
            self.active_detectors[name] = {
                'enabled': config.get('enabled', True),
                'patterns': config.get('patterns', []),
                'tier': 'custom'
            }

    def _compile_patterns(self):
        """Compile regex patterns for all enabled detectors."""
        self.compiled_patterns = {}
        
        for name, config in self.active_detectors.items():
            if config['enabled'] and config['patterns']:
                self.compiled_patterns[name] = re.compile(
                    '|'.join(config['patterns']), 
                    re.I
                )
        
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
            raise EvidenceError(
                message="Failed to parse Telegram update",
                details={
                    "error_type": type(e).__name__,
                    "update_keys": sorted(update.keys()),
                },
            ) from e
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a message event with threat detection."""
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        text = message.get("text", "") or ""
        user_id = str(from_user.get("id", "unknown"))
        msg_timestamp = message.get("date", time.time())

        message_times = self._user_message_times[user_id]
        while message_times and msg_timestamp - message_times[0] > 60:
            message_times.popleft()
        message_times.append(msg_timestamp)
        message_velocity = len(message_times)

        # Calculate content similarity (avg Jaccard against last 10 messages)
        content_similarity = self._calc_content_similarity(user_id, text)
        
        # Analyze content for threats (pass similarity for mirror detection)
        threat_analysis = self._analyze_content(text, content_similarity)
        self._user_recent_texts[user_id].append(text)

        # Extract scores safely from threat_analysis
        scores = threat_analysis.get("scores", {})

        return {
            "event_type": "message",
            "timestamp": msg_timestamp,
            "payload": {
                "message_id": message.get("message_id"),
                "text": text,
                "has_attachments": bool(message.get("photo") or message.get("video") or message.get("document")),
                "is_reply": message.get("reply_to_message") is not None,
                "chat_type": chat.get("type"),
            },
            "features": {
                "text_length": len(text),
                # Threat indicator scores (correctly mapped from threat_analysis)
                "torrent_indicators": scores.get("torrent_sharing", 0.0),
                "crypto_mining_indicators": scores.get("crypto_mining", 0.0),
                "vnc_indicators": scores.get("remote_access", 0.0),
                "copyright_indicators": scores.get("copyright_violation", 0.0),
                "illegal_indicators": scores.get("illegal_content", 0.0),
                "mirrored_content_score": scores.get("mirrored_content", 0.0),
                # Behavioral signals — now actually calculated
                "message_velocity": message_velocity,
                "content_similarity": content_similarity,
            },
            "signals": {
                # Signals for the role pipeline
                "message_velocity": message_velocity,
                "content_similarity": content_similarity,
                "torrent_indicators": scores.get("torrent_sharing", 0.0),
                "crypto_mining_indicators": scores.get("crypto_mining", 0.0),
                "vnc_indicators": scores.get("remote_access", 0.0),
                "copyright_indicators": scores.get("copyright_violation", 0.0),
                "illegal_indicators": scores.get("illegal_content", 0.0),
                "mirrored_content_score": scores.get("mirrored_content", 0.0),
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
    
    def _analyze_content(self, text: str, content_similarity: float = 0.0) -> Dict[str, Any]:
        """Analyze message content for specific threat categories with tenant configuration."""
        text_lower = text.lower()
        
        # Initialize results
        results = {
            "threats_detected": [],
            "scores": {},
            "matches": {}
        }
        
        # Analyze each enabled detector
        for detector_name, config in self.active_detectors.items():
            if not config['enabled']:
                continue
            
            pattern = self.compiled_patterns.get(detector_name)
            if not pattern:
                continue
            
            matches = pattern.findall(text_lower)
            score = min(1.0, len(matches) * 0.25)  # Require multiple matches for higher score
            
            results["scores"][detector_name] = score
            results["matches"][detector_name] = matches
            
            # Determine if threat is detected based on tier-specific thresholds
            if score > 0:
                if config['tier'] == 'core':
                    # Core threats: require stronger signal to reduce false positives
                    if score >= 0.5:
                        results["threats_detected"].append(detector_name)
                else:
                    # Policy/custom threats: standard threshold
                    if score >= 0.5:
                        results["threats_detected"].append(detector_name)
        
        # Mirror detection (improved - requires multiple signals to reduce false positives)
        mirrored_score = 0.0
        # Only flag as mirror if text is long AND contains multiple promotional keywords
        # AND has high content similarity (bot-like repetition)
        promotional_keywords = sum(1 for word in ["join", "channel", "subscribe", "follow", "link", "free", "gift", "promo"] if word in text_lower)
        if len(text) > 150 and promotional_keywords >= 2:
            # Additional signal: check content similarity for spam pattern
            if content_similarity > 0.6:  # Requires actual repetitive behavior
                mirrored_score = 0.7
                if mirrored_score > 0.6:
                    results["threats_detected"].append("mirrors_userbots")
        results["scores"]["mirrored_content"] = mirrored_score
        
        return results
        
        return results
    
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
                "illegal_indicators": 0.0,
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
        """
        Estimate account age in days from Telegram user ID.

        Telegram user IDs are roughly sequential and monotonically increasing.
        We can estimate registration era from known ID ranges:
          < 100_000        : 2013 era (~4000+ days ago)
          < 10_000_000     : 2014-2016 (~2500-3500 days)
          < 100_000_000    : 2016-2018 (~1500-2500 days)
          < 1_000_000_000  : 2018-2021 (~500-1500 days)
          >= 1_000_000_000 : 2021+     (~0-500 days, treat as new)
        Returns a rough midpoint estimate. Not exact but far better than always 30.
        """
        user_id = user.get("id", 0) if isinstance(user, dict) else 0
        if not user_id:
            return 30
        if user_id < 100_000:
            return 4000
        elif user_id < 10_000_000:
            return 3000
        elif user_id < 100_000_000:
            return 2000
        elif user_id < 1_000_000_000:
            return 900
        else:
            return 120  # Likely recent account — treat as higher risk

    def _calc_content_similarity(self, user_id: str, text: str) -> float:
        """
        Calculate Jaccard similarity between current message and user's recent messages.

        Returns a float 0-1 where 1.0 means the message is identical to all recent ones
        (strong spam/mirror signal) and 0.0 means completely unique content.
        """
        if not text or user_id not in self._user_recent_texts:
            return 0.0
        recent = list(self._user_recent_texts[user_id])
        if not recent:
            return 0.0
        current_words = set(text.lower().split())
        if not current_words:
            return 0.0
        similarities = []
        for prev in recent:
            prev_words = set(prev.lower().split())
            if not prev_words:
                continue
            intersection = len(current_words & prev_words)
            union = len(current_words | prev_words)
            similarities.append(intersection / union if union else 0.0)
        return round(sum(similarities) / len(similarities), 3) if similarities else 0.0

    def _calc_entropy(self, text: str) -> float:
        """Calculate username entropy for bot detection."""
        if not text:
            return 0.0
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        entropy = -sum(f/len(text) * math.log2(f/len(text)) for f in freq.values() if f > 0)
        return round(entropy, 2)
    
    def _get_warning_count(self, user_id: int) -> int:
        """Get number of previous warnings for this user from database."""
        if not user_id:
            return 0
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) as warning_count FROM user_warnings WHERE user_id = %s",
                        (user_id,)
                    )
                    result = cur.fetchone()
                    return result.get("warning_count", 0) if result else 0
        except Exception as e:
            logger.warning(f"Failed to get warning count for user {user_id}: {e}")
            return 0
    
    def build_response(self, evaluation_result: Dict[str, Any], tenant_id: str = None, user_id: int = None) -> Dict[str, Any]:
        """
        Convert TruePresence result to Telegram action.

        Args:
            evaluation_result: Result from orchestrator.evaluate()
            tenant_id: Optional tenant identifier for context
            user_id: Optional user identifier for rate limiting

        Returns:
            Action dictionary for Telegram bot to execute
        """
        import time as time_module
        current_time = time_module.time()
        
        # Check rate limit for ban actions
        if user_id is not None:
            last_ban_time = _ban_actions.get(user_id, 0)
            if current_time - last_ban_time < BAN_COOLDOWN_SECONDS:
                # Rate limited - downgrade to alert instead of immediate ban
                logger.info(f"Rate-limited ban for user {user_id}, downgrading to alert")
                return {
                    "action": "alert_admin",
                    "reason": f"Rate-limited: {evaluation_result.get('risk_factors', [])}",
                    "confidence": evaluation_result.get("confidence", 0.0),
                    "tenant_id": tenant_id,
                    "rate_limited": True
                }
        
        state = evaluation_result.get("state")
        decision = evaluation_result.get("decision", "allow")
        confidence = evaluation_result.get("confidence", 0.0)
        human_prob = evaluation_result.get("human_probability", 0.5)
        
        # Get threat categories if available
        threat_categories = evaluation_result.get("threat_categories", [])
        block_reason = evaluation_result.get("block_reason", "")
        
        if state == "EJECT":
            # Track ban action for rate limiting
            if user_id is not None:
                _ban_actions[user_id] = current_time
            return {
                "action": "ban",
                "reason": block_reason or "Deterministic policy violation",
                "confidence": confidence,
                "threat_categories": threat_categories,
                "tenant_id": tenant_id,
            }
        if state == "RESTRICT":
            return {
                "action": "kick",
                "reason": block_reason or "Restricted pending further review",
                "confidence": confidence,
                "threat_categories": threat_categories,
                "tenant_id": tenant_id,
            }
        if state == "STEP_UP_AUTH":
            return {
                "action": "challenge",
                "reason": "Additional verification required",
                "confidence": confidence,
                "tenant_id": tenant_id,
            }
        if state == "OBSERVE":
            return {
                "action": "allow",
                "reason": "Allowed with monitoring",
                "confidence": confidence,
                "tenant_id": tenant_id,
                "monitor": True,
            }

        # More aggressive blocking for confirmed threats
        if threat_categories:
            # Any confirmed threat category = immediate block (with rate limiting)
            if confidence > 0.6:
                if user_id is not None:
                    _ban_actions[user_id] = current_time
                return {
                    "action": "ban",
                    "reason": block_reason or f"Threat detected: {', '.join(threat_categories)}",
                    "confidence": confidence,
                    "threat_categories": threat_categories,
                    "tenant_id": tenant_id
                }
        
        if decision == "block" and confidence > 0.8:
            if user_id is not None:
                _ban_actions[user_id] = current_time
            return {
                "action": "ban",
                "reason": block_reason or f"Bot detected ({human_prob:.0%} human probability)",
                "confidence": confidence,
                "tenant_id": tenant_id
            }
        elif decision == "block" and confidence > 0.6:
            return {
                "action": "kick",
                "reason": block_reason or f"Suspicious ({human_prob:.0%} human probability)",
                "confidence": confidence,
                "tenant_id": tenant_id
            }
        elif decision == "challenge":
            return {
                "action": "challenge",
                "reason": "Verification required",
                "confidence": confidence,
                "tenant_id": tenant_id
            }
        elif decision == "review":
            return {
                "action": "alert_admin",
                "reason": f"Review needed - {evaluation_result.get('risk_factors', [])}",
                "confidence": confidence,
                "tenant_id": tenant_id
            }
        
        return {
            "action": "allow",
            "confidence": confidence,
            "tenant_id": tenant_id
        }
    
