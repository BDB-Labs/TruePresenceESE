"""
Telegram Adapter for TruePresence

Converts Telegram webhook events into TruePresence evaluation events.
Includes detection for: Mirrors/Userbots, Crypto Miners, DMCA, Torrents, VNC, Illegal Content
"""

from __future__ import annotations

import logging
import math
import re
import statistics
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional

from truepresence.adapters.telegram_models import TelegramAction, TelegramEvent
from truepresence.db import get_db
from truepresence.detectors.telegram_community import run_telegram_community_detectors
from truepresence.exceptions import EvidenceError
from truepresence.safety import (
    ProviderRiskSignal,
    TelegramSafetyFeatures,
    evaluate_telegram_safety_escalation,
)
from truepresence.surfaces.telegram.community import TelegramCommunityFeatures

logger = logging.getLogger(__name__)

# Rate limiting for ban actions
_ban_actions: Dict[str, float] = {}  # tenant_id:user_id -> timestamp
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
                r'\bcp\b(?!\s*(?:certificate|panel|apache|copyright|cpu|cpus|center|connection))',
                r'\blolita\b(?!\s*(?:book|novel|nabokov|fashion))',
                r'\bpedo\b(?!\s*(?:bear|file|meter|pedometry))',
            ]
        },
        'illegal_content': {
            'enabled': True,  # Always enabled
            'configurable': False,
            'patterns': [
                r'\b(buy|purchase|order|get)\s+.*\b(drugs|narcotics|opioids|cocaine|heroin|meth)\b',
                r'\b(fake|forged|counterfeit)\s+.*\b(id|passport|drivers\s+license|credit\s+card)\b',
                r'\bcarding\b',
                r'\bhacking\s+.*(service|tool|tutorial)\b',
                r'\b(weapon|firearm|gun)\s+.*(sale|buy|purchase)\b',
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

        # Metadata-only Telegram community behavior state.
        self._user_chat_join_times: Dict[tuple[str, str], float] = {}
        self._user_chat_first_message_ms: Dict[tuple[str, str], float] = {}
        self._user_chat_first_media_ms: Dict[tuple[str, str], float] = {}
        self._user_chat_first_link_ms: Dict[tuple[str, str], float] = {}
        self._chat_join_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=250))
        self._chat_message_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=250))
        self._user_joined_groups: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self._user_media_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._chat_media_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=250))

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
        """
        try:
            # Handle different update types
            if "message" in update:
                event_data = self._parse_message(update["message"])
            elif "edited_message" in update:
                event_data = self._parse_message(update["edited_message"])
            elif "chat_member" in update:
                event_data = self._parse_chat_member(update["chat_member"])
            elif "my_chat_member" in update:
                event_data = self._parse_chat_member(update["my_chat_member"])
            else:
                return None
            
            return TelegramEvent(**event_data).model_dump()
                
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
        
        # Standardize to Unix timestamp for internal processing
        msg_timestamp = message.get("date", time.time())
        message_velocity = self._calc_message_velocity(user_id, msg_timestamp)

        # Calculate content similarity (avg Jaccard against last 10 messages)
        content_similarity = self._calc_content_similarity(user_id, text)
        
        # Analyze content for threats (pass similarity for mirror detection)
        threat_analysis = self._analyze_content(text, content_similarity)
        self._user_recent_texts[user_id].append(text)

        # Extract scores safely from threat_analysis
        scores = threat_analysis.get("scores", {})
        community_features = self._build_community_features_for_message(
            user_id=user_id,
            chat_id=str(chat.get("id", "unknown")),
            timestamp=msg_timestamp,
            message=message,
        )
        community_signals = run_telegram_community_detectors(community_features)
        community = self._community_context(community_features, community_signals)
        community_feature_scores = self._community_feature_scores(community_features)
        community_signal_scores = {
            f"telegram_community_{signal.reason_code}": signal.confidence
            for signal in community_signals
        }
        safety_features = self._build_safety_features_for_message(
            user_id=user_id,
            chat_id=str(chat.get("id", "unknown")),
            timestamp=msg_timestamp,
            message=message,
            community_features=community_features,
            account_age_days=self._estimate_account_age(from_user),
        )
        provider_signal = self._provider_signal_for_media(safety_features)
        safety_escalation = evaluate_telegram_safety_escalation(
            safety_features,
            provider_signal=provider_signal,
        )
        safety = self._safety_context(safety_escalation, safety_features)

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
                **community_feature_scores,
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
                **community_signal_scores,
            },
            "context": {
                "platform": "telegram",
                "user_id": from_user.get("id"),
                "username": from_user.get("username", ""),
                "is_bot": from_user.get("is_bot", False),
                "group_id": chat.get("id"),
                "telegram_community": community,
                "telegram_safety": safety,
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
        user_id = str(user.get("id", "unknown"))
        chat_id = str(chat.get("id", "unknown"))
        timestamp = float(chat_member.get("date", 0) or time.time())
        if event_type == "member_join":
            self._record_join_metadata(user_id, chat_id, timestamp)
        community_features = self._build_community_features_for_member(user_id, chat_id, timestamp)
        community_signals = run_telegram_community_detectors(community_features)
        community = self._community_context(community_features, community_signals)
        
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
                **self._community_feature_scores(community_features),
            },
            "signals": {
                "torrent_indicators": 0.0,
                "crypto_mining_indicators": 0.0,
                "vnc_indicators": 0.0,
                "copyright_indicators": 0.0,
                "illegal_indicators": 0.0,
                "mirrored_content_score": 0.0,
                **{
                    f"telegram_community_{signal.reason_code}": signal.confidence
                    for signal in community_signals
                },
            },
            "context": {
                "platform": "telegram",
                "user_id": user.get("id"),
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
                "is_bot": user.get("is_bot", False),
                "group_id": chat.get("id"),
                "group_title": chat.get("title", ""),
                "telegram_community": community,
            },
            "threat_analysis": {
                "threats_detected": []
            }
        }
    
    def _estimate_account_age(self, user: Dict[str, Any]) -> int:
        """
        Estimate account age in days from Telegram user ID.
        Uses updated 2024/2025 ID ranges.
        """
        user_id = user.get("id", 0) if isinstance(user, dict) else 0
        if not user_id:
            return 30
        if user_id < 100_000:
            return 4500
        elif user_id < 10_000_000:
            return 3500
        elif user_id < 100_000_000:
            return 2500
        elif user_id < 500_000_000:
            return 1200
        elif user_id < 1_000_000_000:
            return 600
        elif user_id < 5_000_000_000:
            return 180
        else:
            return 30  # Very new account

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

    def _calc_message_velocity(self, user_id: str, timestamp: float) -> float:
        """Calculate messages-per-minute for this user over a rolling 60-second window."""
        if not user_id:
            return 0.0
        now = float(timestamp or time.time())
        recent = self._user_message_times[user_id]
        recent.append(now)
        cutoff = now - 60
        while recent and recent[0] < cutoff:
            recent.popleft()
        return round(len(recent), 3)

    def _record_join_metadata(self, user_id: str, chat_id: str, timestamp: float) -> None:
        key = (user_id, chat_id)
        self._user_chat_join_times[key] = timestamp
        self._user_chat_first_message_ms.pop(key, None)
        self._user_chat_first_media_ms.pop(key, None)
        self._user_chat_first_link_ms.pop(key, None)

        chat_joins = self._chat_join_times[chat_id]
        chat_joins.append(timestamp)
        cutoff = timestamp - 60
        while chat_joins and chat_joins[0] < cutoff:
            chat_joins.popleft()

        joined_groups = self._user_joined_groups[user_id]
        if chat_id not in joined_groups:
            joined_groups.append(chat_id)

    def _build_community_features_for_member(
        self,
        user_id: str,
        chat_id: str,
        timestamp: float,
    ) -> TelegramCommunityFeatures:
        return TelegramCommunityFeatures(
            joined_within_cluster_count=self._joined_within_cluster_count(chat_id, timestamp),
            group_hop_count=len(set(self._user_joined_groups.get(user_id, []))),
            link_present=False,
            media_present=False,
        )

    def _build_community_features_for_message(
        self,
        *,
        user_id: str,
        chat_id: str,
        timestamp: float,
        message: Dict[str, Any],
    ) -> TelegramCommunityFeatures:
        link_present = self._message_has_link_entity(message)
        media_present = self._message_has_media(message)
        key = (user_id, chat_id)
        join_time = self._user_chat_join_times.get(key)

        join_to_first_message_ms = self._first_action_latency_ms(
            store=self._user_chat_first_message_ms,
            key=key,
            join_time=join_time,
            timestamp=timestamp,
            condition=True,
        )
        join_to_first_media_ms = self._first_action_latency_ms(
            store=self._user_chat_first_media_ms,
            key=key,
            join_time=join_time,
            timestamp=timestamp,
            condition=media_present,
        )
        join_to_first_link_ms = self._first_action_latency_ms(
            store=self._user_chat_first_link_ms,
            key=key,
            join_time=join_time,
            timestamp=timestamp,
            condition=link_present,
        )
        interval_summary = self._message_interval_summary(user_id)
        synchronized_peer_count = self._synchronized_peer_count(chat_id, user_id, timestamp)
        self._record_message_cluster(chat_id, user_id, timestamp)

        return TelegramCommunityFeatures(
            join_to_first_message_ms=join_to_first_message_ms,
            join_to_first_media_ms=join_to_first_media_ms,
            join_to_first_link_ms=join_to_first_link_ms,
            message_count_window=interval_summary["message_count_window"],
            burst_count=interval_summary["burst_count"],
            mean_message_interval_ms=interval_summary["mean_message_interval_ms"],
            message_interval_stddev_ms=interval_summary["message_interval_stddev_ms"],
            joined_within_cluster_count=self._joined_within_cluster_count(chat_id, timestamp),
            synchronized_peer_count=synchronized_peer_count,
            group_hop_count=len(set(self._user_joined_groups.get(user_id, []))),
            link_present=link_present,
            media_present=media_present,
        )

    def _first_action_latency_ms(
        self,
        *,
        store: Dict[tuple[str, str], float],
        key: tuple[str, str],
        join_time: float | None,
        timestamp: float,
        condition: bool,
    ) -> float | None:
        if not condition or join_time is None:
            return store.get(key)
        if key not in store:
            store[key] = max(0.0, (float(timestamp) - float(join_time)) * 1000)
        return store[key]

    def _message_interval_summary(self, user_id: str) -> Dict[str, int | float | None]:
        recent = list(self._user_message_times.get(user_id, []))
        intervals = [
            max(0.0, (right - left) * 1000)
            for left, right in zip(recent, recent[1:])
        ]
        if not intervals:
            return {
                "message_count_window": len(recent),
                "burst_count": 0,
                "mean_message_interval_ms": None,
                "message_interval_stddev_ms": None,
            }
        return {
            "message_count_window": len(recent),
            "burst_count": sum(1 for interval in intervals if interval <= 2_000),
            "mean_message_interval_ms": round(sum(intervals) / len(intervals), 3),
            "message_interval_stddev_ms": round(statistics.pstdev(intervals), 3)
            if len(intervals) > 1
            else 0.0,
        }

    def _joined_within_cluster_count(self, chat_id: str, timestamp: float) -> int:
        recent = self._chat_join_times.get(chat_id)
        if not recent:
            return 0
        cutoff = float(timestamp) - 60
        while recent and recent[0] < cutoff:
            recent.popleft()
        return len(recent)

    def _synchronized_peer_count(self, chat_id: str, user_id: str, timestamp: float) -> int:
        recent = self._chat_message_times[chat_id]
        cutoff = float(timestamp) - 3
        while recent and recent[0][0] < cutoff:
            recent.popleft()
        return len({peer_id for _, peer_id in recent if peer_id != user_id})

    def _record_message_cluster(self, chat_id: str, user_id: str, timestamp: float) -> None:
        recent = self._chat_message_times[chat_id]
        recent.append((float(timestamp), user_id))
        cutoff = float(timestamp) - 60
        while recent and recent[0][0] < cutoff:
            recent.popleft()

    def _build_safety_features_for_message(
        self,
        *,
        user_id: str,
        chat_id: str,
        timestamp: float,
        message: Dict[str, Any],
        community_features: TelegramCommunityFeatures,
        account_age_days: int,
    ) -> TelegramSafetyFeatures:
        media_present = self._message_has_media(message)
        media_summary = self._media_interval_summary(user_id, timestamp, media_present)
        synchronized_media_peer_count = self._synchronized_media_peer_count(
            chat_id,
            user_id,
            timestamp,
        )
        if media_present:
            self._record_media_cluster(chat_id, user_id, timestamp)

        return TelegramSafetyFeatures(
            chat_id=message.get("chat", {}).get("id"),
            message_id=message.get("message_id"),
            sender_id=message.get("from", {}).get("id"),
            event_timestamp=timestamp,
            event_type="message",
            media_present=media_present,
            join_to_first_media_ms=community_features.join_to_first_media_ms,
            media_count_window=media_summary["media_count_window"],
            media_burst_count=media_summary["media_burst_count"],
            synchronized_media_peer_count=synchronized_media_peer_count if media_present else 0,
            group_hop_count=community_features.group_hop_count or 0,
            account_age_days=account_age_days,
            rapid_delete_repost_count=0,
        )

    def _media_interval_summary(
        self,
        user_id: str,
        timestamp: float,
        media_present: bool,
    ) -> Dict[str, int | float | None]:
        recent = self._user_media_times[user_id]
        if media_present:
            recent.append(float(timestamp))
        cutoff = float(timestamp) - 60
        while recent and recent[0] < cutoff:
            recent.popleft()

        media_times = list(recent)
        intervals = [
            max(0.0, (right - left) * 1000)
            for left, right in zip(media_times, media_times[1:])
        ]
        return {
            "media_count_window": len(media_times),
            "media_burst_count": sum(1 for interval in intervals if interval <= 10_000),
        }

    def _synchronized_media_peer_count(self, chat_id: str, user_id: str, timestamp: float) -> int:
        recent = self._chat_media_times[chat_id]
        cutoff = float(timestamp) - 10
        while recent and recent[0][0] < cutoff:
            recent.popleft()
        return len({peer_id for _, peer_id in recent if peer_id != user_id})

    def _record_media_cluster(self, chat_id: str, user_id: str, timestamp: float) -> None:
        recent = self._chat_media_times[chat_id]
        recent.append((float(timestamp), user_id))
        cutoff = float(timestamp) - 60
        while recent and recent[0][0] < cutoff:
            recent.popleft()

    def _provider_signal_for_media(
        self,
        features: TelegramSafetyFeatures,
    ) -> ProviderRiskSignal | None:
        if not features.media_present:
            return None
        provider = self.tenant_config.get("safety_provider") or self.tenant_config.get("media_risk_provider")
        if provider is None:
            return None
        metadata = {
            "chat_id": features.chat_id,
            "message_id": features.message_id,
            "sender_id": features.sender_id,
            "event_timestamp": features.event_timestamp,
            "event_type": features.event_type,
            "media_present": features.media_present,
        }
        result = None
        if hasattr(provider, "assess_telegram_media"):
            result = provider.assess_telegram_media(metadata)
        elif callable(provider):
            result = provider(metadata)
        if result is None:
            return None
        if isinstance(result, ProviderRiskSignal):
            return result
        if isinstance(result, dict):
            return ProviderRiskSignal(**result)
        raise TypeError("safety provider must return ProviderRiskSignal, dict, or None")

    def _safety_context(self, escalation, features: TelegramSafetyFeatures) -> Dict[str, Any]:
        if escalation is None:
            return {
                "reason_codes": [],
                "recommended_action": None,
                "risk": {"score": 0.0, "label": "low"},
                "evidence_card": {
                    "chat_id": features.chat_id,
                    "message_id": features.message_id,
                    "sender_id": features.sender_id,
                    "timestamps": {"event_timestamp": features.event_timestamp},
                    "media_present": features.media_present,
                    "event_type": features.event_type,
                    "reason_codes": [],
                    "risk": {"score": 0.0, "label": "low"},
                    "confidence": 0.0,
                    "risk_label": "low",
                    "recommended_action": None,
                },
            }
        return {
            "reason_codes": list(escalation.reason_codes),
            "recommended_action": escalation.recommended_action,
            "risk": {
                "score": round(escalation.risk_score, 3),
                "label": escalation.risk_label,
            },
            "confidence": round(escalation.confidence, 3),
            "detector_signals": list(escalation.detector_signals),
            "evidence_card": dict(escalation.evidence_card),
        }

    def _message_has_link_entity(self, message: Dict[str, Any]) -> bool:
        for key in ("entities", "caption_entities"):
            entities = message.get(key) or []
            for entity in entities:
                if isinstance(entity, dict) and entity.get("type") in {"url", "text_link"}:
                    return True
        return False

    def _message_has_media(self, message: Dict[str, Any]) -> bool:
        media_keys = {
            "photo",
            "video",
            "document",
            "animation",
            "audio",
            "voice",
            "video_note",
            "sticker",
        }
        return any(bool(message.get(key)) for key in media_keys)

    def _community_context(
        self,
        features: TelegramCommunityFeatures,
        signals,
    ) -> Dict[str, Any]:
        return {
            "features": features.model_dump(exclude_none=True),
            "reason_codes": [signal.reason_code for signal in signals],
            "detector_signals": [signal.model_dump() for signal in signals],
        }

    def _community_feature_scores(self, features: TelegramCommunityFeatures) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for key, value in features.model_dump(exclude_none=True).items():
            if isinstance(value, bool):
                scores[f"telegram_community_{key}"] = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                scores[f"telegram_community_{key}"] = float(value)
        return scores
    
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
    
    def build_response(self, evaluation_result: Dict[str, Any], tenant_id: str = None, user_id: int = None) -> TelegramAction:
        """
        Convert TruePresence result to Telegram action.
        Maps removal factors (reason_codes/threat_categories) to specific enforcement actions.
        """
        current_time = time.time()
        
        # Check rate limit for ban actions
        if user_id is not None:
            ban_key = f"{tenant_id}:{user_id}"
            last_ban_time = _ban_actions.get(ban_key, 0)
            if current_time - last_ban_time < BAN_COOLDOWN_SECONDS:
                logger.info(f"Rate-limited ban for user {user_id}, downgrading to alert")
                return TelegramAction(
                    action="alert_admin",
                    reason=f"Rate-limited: {evaluation_result.get('risk_factors', [])}",
                    confidence=evaluation_result.get("confidence", 0.0),
                    tenant_id=tenant_id,
                    rate_limited=True,
                )
        
        state = evaluation_result.get("state")
        decision = evaluation_result.get("decision", "allow")
        confidence = evaluation_result.get("confidence", 0.0)
        human_prob = evaluation_result.get("human_probability", 0.5)
        threat_categories = evaluation_result.get("threat_categories", [])
        reason_codes = evaluation_result.get("reason_codes", [])
        block_reason = evaluation_result.get("block_reason", "")

        # Removal Workflow Logic: Map determination factors to actions
        critical_factors = {'child_exploitation', 'illegal_content'}
        policy_factors = {'copyright_violation', 'torrent_sharing', 'crypto_mining', 'remote_access'}
        
        # 1. Critical Security Violations -> Immediate Ban
        if any(cat in critical_factors for cat in threat_categories) or any(code in critical_factors for code in reason_codes):
            if user_id is not None:
                _ban_actions[user_id] = current_time
            return TelegramAction(
                action="ban",
                reason=f"CRITICAL SECURITY VIOLATION: {block_reason or 'Illegal content detected'}",
                confidence=confidence,
                threat_categories=threat_categories,
                tenant_id=tenant_id,
            )

        # 2. Policy Violations -> Ban if high confidence, else Kick/Warn
        if any(cat in policy_factors for cat in threat_categories) or any(code in policy_factors for code in reason_codes):
            if confidence > 0.8:
                if user_id is not None:
                    _ban_actions[user_id] = current_time
                return TelegramAction(
                    action="ban",
                    reason=f"Policy Violation: {block_reason or 'Repeated policy breach'}",
                    confidence=confidence,
                    threat_categories=threat_categories,
                    tenant_id=tenant_id,
                )
            elif confidence > 0.5:
                return TelegramAction(
                    action="kick",
                    reason=f"Policy Warning: {block_reason or 'Suspicious activity'}",
                    confidence=confidence,
                    threat_categories=threat_categories,
                    tenant_id=tenant_id,
                )

        # 3. Engine State-based Enforcement
        if state == "EJECT":
            if user_id is not None:
                _ban_actions[user_id] = current_time
            return TelegramAction(
                action="ban",
                reason=block_reason or "Deterministic policy violation",
                confidence=confidence,
                threat_categories=threat_categories,
                tenant_id=tenant_id,
            )
        if state == "RESTRICT":
            return TelegramAction(
                action="kick",
                reason=block_reason or "Restricted pending further review",
                confidence=confidence,
                threat_categories=threat_categories,
                tenant_id=tenant_id,
            )
        if state == "STEP_UP_AUTH":
            return TelegramAction(
                action="challenge",
                reason="Additional verification required",
                confidence=confidence,
                tenant_id=tenant_id,
            )
        if state == "OBSERVE":
            return TelegramAction(
                action="allow",
                reason="Allowed with monitoring",
                confidence=confidence,
                tenant_id=tenant_id,
                # monitor = True is handled in metadata or a custom field if needed
            )
        
        # 4. General Bot Detection
        if decision == "block" and confidence > 0.8:
            if user_id is not None:
                _ban_actions[user_id] = current_time
            return TelegramAction(
                action="ban",
                reason=block_reason or f"Bot detected ({human_prob:.0%} human probability)",
                confidence=confidence,
                tenant_id=tenant_id
            )
        elif decision == "block" and confidence > 0.6:
            return TelegramAction(
                action="kick",
                reason=block_reason or f"Suspicious ({human_prob:.0%} human probability)",
                confidence=confidence,
                tenant_id=tenant_id
            )
        elif decision == "challenge":
            return TelegramAction(
                action="challenge",
                reason="Verification required",
                confidence=confidence,
                tenant_id=tenant_id,
            )
        elif decision == "review":
            return TelegramAction(
                action="alert_admin",
                reason=f"Review needed - {evaluation_result.get('risk_factors', [])}",
                confidence=confidence,
                tenant_id=tenant_id
            )
        
        return TelegramAction(
            action="allow",
            confidence=confidence,
            tenant_id=tenant_id
        )

        
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
                _ban_actions[f"{tenant_id}:{user_id}"] = current_time
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
                    _ban_actions[f"{tenant_id}:{user_id}"] = current_time
                return {
                    "action": "ban",
                    "reason": block_reason or f"Threat detected: {', '.join(threat_categories)}",
                    "confidence": confidence,
                    "threat_categories": threat_categories,
                    "tenant_id": tenant_id
                }
        
        if decision == "block" and confidence > 0.8:
            if user_id is not None:
                _ban_actions[f"{tenant_id}:{user_id}"] = current_time
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
    
