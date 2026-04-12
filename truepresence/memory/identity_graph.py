"""
Identity Graph for TruePresence

This module provides persistent cross-session memory by building a graph
that connects similar sessions, enabling bot clustering and detection
across multiple sessions.
"""

import numpy as np
from typing import Dict, Any, List, Set, Optional
from collections import defaultdict
import hashlib


class IdentityGraph:
    """
    Identity Graph for cross-session bot clustering and detection.
    
    This class builds a graph that connects sessions with similar behavioral patterns,
    enabling detection of bots that appear across multiple sessions.
    """
    
    def __init__(self, similarity_threshold: float = 0.75):
        """
        Initialize Identity Graph.
        
        Args:
            similarity_threshold: Threshold for considering sessions similar (0-1)
        """
        self.similarity_threshold = similarity_threshold
        self.sessions = {}  # session_id -> session_data
        self.graph = defaultdict(set)  # session_id -> set of connected session_ids
        self.session_features = {}  # session_id -> feature_vector
        
    def _hash_session_id(self, session_id: str) -> str:
        """Create consistent hash for session ID."""
        return hashlib.md5(session_id.encode()).hexdigest()
        
    def _extract_features(self, session: Dict[str, Any]) -> List[float]:
        """
        Extract behavioral features from a session for similarity comparison.
        
        Args:
            session: Session dictionary
            
        Returns:
            Feature vector as list of floats
        """
        features = []
        
        # Extract basic session features
        duration = session.get("duration", 0)
        event_count = session.get("event_count", 0)
        avg_interval = session.get("avg_interval", 1.0)
        
        features.extend([
            duration,
            event_count,
            avg_interval
        ])
        
        # Extract behavioral patterns if available
        behavior = session.get("behavior", {})
        mouse_variance = behavior.get("mouse_variance", 0.5)
        typing_speed = behavior.get("typing_speed", 0.5)
        timing_consistency = behavior.get("timing_consistency", 0.5)
        
        features.extend([
            mouse_variance,
            typing_speed,
            timing_consistency
        ])
        
        # Extract detection scores if available
        detection = session.get("detection", {})
        human_prob = detection.get("human_probability", 0.5)
        confidence = detection.get("confidence", 0.5)
        
        features.extend([
            human_prob,
            confidence
        ])
        
        # Normalize features to [0,1] range
        normalized_features = []
        for feature in features:
            if isinstance(feature, (int, float)):
                # Simple min-max normalization assuming reasonable ranges
                if feature > 1000:  # Likely a duration or count
                    normalized = min(feature / 10000.0, 1.0)
                else:
                    normalized = min(max(feature, 0.0), 1.0)
                normalized_features.append(float(normalized))
            else:
                normalized_features.append(0.5)
                
        return normalized_features
        
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First feature vector
            vec2: Second feature vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if not vec1 or not vec2:
            return 0.0
            
        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)
        
        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
        
    def add_session(self, session_id: str, session: Dict[str, Any]):
        """
        Add a session to the identity graph.
        
        Args:
            session_id: Unique session identifier
            session: Session dictionary containing behavioral data
        """
        hashed_id = self._hash_session_id(session_id)
        
        # Store session data
        self.sessions[hashed_id] = session
        
        # Extract and store features
        features = self._extract_features(session)
        self.session_features[hashed_id] = features
        
        # Find similar sessions and build connections
        self._build_connections(hashed_id)
        
    def _build_connections(self, session_id: str):
        """
        Build connections between similar sessions.
        
        Args:
            session_id: Session ID to connect with similar sessions
        """
        if session_id not in self.session_features:
            return
            
        target_features = self.session_features[session_id]
        
        # Compare with all existing sessions
        for existing_id, existing_features in self.session_features.items():
            if existing_id == session_id:
                continue
                
            similarity = self._cosine_similarity(target_features, existing_features)
            
            # Create connection if similarity exceeds threshold
            if similarity >= self.similarity_threshold:
                self.graph[session_id].add(existing_id)
                self.graph[existing_id].add(session_id)
    
    def get_connected_sessions(self, session_id: str) -> Set[str]:
        """
        Get sessions connected to the given session.
        
        Args:
            session_id: Session ID to find connections for
            
        Returns:
            Set of connected session IDs
        """
        hashed_id = self._hash_session_id(session_id)
        return self.graph.get(hashed_id, set())
        
    def get_session_cluster(self, session_id: str) -> Set[str]:
        """
        Get the entire cluster of connected sessions (transitive connections).
        
        Args:
            session_id: Session ID to find cluster for
            
        Returns:
            Set of all session IDs in the same cluster
        """
        hashed_id = self._hash_session_id(session_id)
        cluster = set()
        visited = set()
        
        stack = [hashed_id]
        
        while stack:
            current = stack.pop()
            if current in visited:
                continue
                
            visited.add(current)
            cluster.add(current)
            
            # Add all connected sessions to explore
            for neighbor in self.graph.get(current, set()):
                if neighbor not in visited:
                    stack.append(neighbor)
                    
        return cluster
        
    def get_session_risk(self, session_id: str) -> float:
        """
        Calculate risk score based on connected sessions.
        
        Args:
            session_id: Session ID to calculate risk for
            
        Returns:
            Risk score between 0 and 1
        """
        hashed_id = self._hash_session_id(session_id)
        
        if hashed_id not in self.sessions:
            return 0.5
            
        # Get cluster of connected sessions
        cluster = self.get_session_cluster(hashed_id)
        
        if not cluster:
            return 0.5
            
        # Calculate average detection scores from cluster
        total_risk = 0.0
        bot_count = 0
        
        for cluster_id in cluster:
            cluster_session = self.sessions[cluster_id]
            detection = cluster_session.get("detection", {})
            bot_prob = detection.get("bot_probability", 0.5)
            confidence = detection.get("confidence", 0.5)
            
            # Weighted risk contribution
            risk_contribution = bot_prob * confidence
            total_risk += risk_contribution
            
            if bot_prob > 0.7:
                bot_count += 1
                
        # Calculate cluster risk score
        cluster_size = len(cluster)
        avg_risk = total_risk / cluster_size
        
        # Boost risk if multiple sessions in cluster were detected as bots
        if bot_count > 1:
            risk_boost = min(bot_count / cluster_size, 0.8)
            final_risk = min(avg_risk + risk_boost, 1.0)
        else:
            final_risk = avg_risk
            
        return float(final_risk)
        
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session dictionary or None if not found
        """
        hashed_id = self._hash_session_id(session_id)
        return self.sessions.get(hashed_id)