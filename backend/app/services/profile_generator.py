"""Generate agent personas from knowledge graph entities using LLM."""

import json
import os
import uuid
from datetime import datetime

from app.config import Config
from app.utils.llm_client import LLMClient
from app.services.entity_reader import EntityReader

# Default values for profile fields when LLM omits them
_PROFILE_DEFAULTS = {
    'name': 'Unknown',
    'username': None,  # generated dynamically
    'bio': '',
    'persona': '',
    'age': 30,
    'gender': 'Unknown',
    'mbti': 'ENFP',
    'profession': 'Unknown',
    'karma': 100,
    'follower_count': 50,
    'friend_count': 10,
    'country': 'United States',
    'interested_topics': [],
    'stance': 'neutral',
    'activity_level': 'medium',
    'posting_frequency': 'a few times per week',
    'tone': 'casual',
    'preferred_topics': [],
}


class ProfileGenerator:
    """Generates agent profiles from knowledge graph entities."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()
        self.entity_reader = EntityReader()

    def generate_profile(self, entity: dict, requirement: str = '') -> dict:
        """Generate a single agent profile from a knowledge graph entity.

        Args:
            entity: Entity dict with id, name, type, description, attributes, edges, neighbors
            requirement: Simulation requirement for context

        Returns:
            Agent profile dict
        """
        context = self._build_entity_context(entity)

        prompt = f"""You are creating a social media user profile for a multi-agent simulation.

Based on the following knowledge graph entity, create a deeply realistic social media persona.

Entity context:
{context}

Simulation requirement: {requirement or 'General social media simulation'}

Generate a JSON profile with ALL of these fields:
{{
  "name": "Full realistic name related to the entity",
  "username": "a_social_media_handle",
  "bio": "Short bio, max 200 characters",
  "persona": "A detailed 2000-character persona description. Include: personality traits and quirks, communication style (formal/casual/sarcastic/earnest), typical social media behavior (lurker vs poster, how they reply, do they use emojis, hashtags), their values and beliefs, what triggers them to engage or argue, their online habits (time of day, device, scroll patterns). Make this feel like a real, complex human being.",
  "age": 25,
  "gender": "male or female or non-binary",
  "mbti": "INTJ (one of 16 MBTI types)",
  "profession": "Their job, role, or occupation",
  "karma": 500,
  "follower_count": 1200,
  "friend_count": 350,
  "country": "Country of residence",
  "interested_topics": ["topic1", "topic2", "topic3"],
  "stance": "Their general stance or viewpoint on key topics",
  "activity_level": "low/medium/high",
  "posting_frequency": "e.g. multiple times daily, daily, a few times per week, weekly, rarely",
  "tone": "e.g. sarcastic, earnest, professional, aggressive, wholesome, neutral",
  "preferred_topics": ["topics they actively post about, not just read"]
}}

Guidelines:
- The persona field MUST be at least 800 characters. Describe HOW this person behaves on social media, not just who they are.
- Include specific social media habits: do they doomscroll? Do they reply to strangers? Do they post OC or reshare? Are they confrontational or diplomatic?
- Age should be realistic (18-80) and consistent with the entity context.
- Karma (0-10000) reflects how established/reputable they are online.
- follower_count (0-50000) and friend_count (0-5000) should be consistent with activity_level.
- The profile should feel like a real person who would naturally discuss or be involved with the entity's domain.
Return ONLY the JSON object."""

        profile = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.8,
        )

        # Ensure required fields with defaults
        for key, default in _PROFILE_DEFAULTS.items():
            if key == 'username':
                profile.setdefault(key, f"user_{uuid.uuid4().hex[:8]}")
            elif key == 'name':
                profile.setdefault(key, entity.get('name', default))
            else:
                profile.setdefault(key, default)

        # Clamp numeric fields to valid ranges
        profile['age'] = max(18, min(80, int(profile.get('age', 30))))
        profile['karma'] = max(0, min(10000, int(profile.get('karma', 100))))
        profile['follower_count'] = max(0, min(50000, int(profile.get('follower_count', 50))))
        profile['friend_count'] = max(0, min(5000, int(profile.get('friend_count', 10))))

        # Truncate text fields to limits
        profile['bio'] = str(profile['bio'])[:Config.PROFILE_BIO_MAX_LENGTH]
        profile['persona'] = str(profile['persona'])[:Config.PROFILE_PERSONA_MAX_LENGTH]

        # Normalize list fields
        for list_field in ('interested_topics', 'preferred_topics'):
            if not isinstance(profile.get(list_field), list):
                profile[list_field] = []

        # Add metadata
        profile['agent_id'] = str(uuid.uuid4())[:8]
        profile['source_entity_id'] = entity.get('id', '')
        profile['source_entity_name'] = entity.get('name', '')
        profile['source_entity_type'] = entity.get('type', '')
        profile['created_at'] = datetime.now().isoformat()

        return profile

    @staticmethod
    def to_twitter_format(profile: dict) -> dict:
        """Convert a profile to Twitter/X-appropriate format.

        Returns a dict with fields matching Twitter's user model.
        """
        return {
            'name': profile.get('name', ''),
            'screen_name': profile.get('username', ''),
            'description': profile.get('bio', ''),
            'location': profile.get('country', ''),
            'followers_count': profile.get('follower_count', 0),
            'friends_count': profile.get('friend_count', 0),
            'verified': profile.get('follower_count', 0) > 10000,
            'profile_persona': profile.get('persona', ''),
            'interested_topics': profile.get('interested_topics', []),
            'stance': profile.get('stance', ''),
            'activity_level': profile.get('activity_level', 'medium'),
            'posting_frequency': profile.get('posting_frequency', ''),
            'tone': profile.get('tone', 'neutral'),
            'agent_id': profile.get('agent_id', ''),
        }

    @staticmethod
    def to_reddit_format(profile: dict) -> dict:
        """Convert a profile to Reddit-appropriate format.

        Returns a dict with fields matching Reddit's user model.
        """
        return {
            'username': profile.get('username', ''),
            'display_name': profile.get('name', ''),
            'bio': profile.get('bio', ''),
            'karma': profile.get('karma', 0),
            'comment_karma': int(profile.get('karma', 0) * 0.6),
            'post_karma': int(profile.get('karma', 0) * 0.4),
            'cake_day': profile.get('created_at', ''),
            'subscribed_subreddits': profile.get('interested_topics', []),
            'profile_persona': profile.get('persona', ''),
            'stance': profile.get('stance', ''),
            'activity_level': profile.get('activity_level', 'medium'),
            'posting_frequency': profile.get('posting_frequency', ''),
            'tone': profile.get('tone', 'neutral'),
            'preferred_topics': profile.get('preferred_topics', []),
            'agent_id': profile.get('agent_id', ''),
        }

    def generate_profiles_batch(
        self,
        graph_id: str,
        requirement: str = '',
        entity_type: str = None,
        max_agents: int = None,
        callback=None,
    ) -> list[dict]:
        """Generate profiles for all entities in a knowledge graph.

        Args:
            graph_id: Knowledge graph identifier
            requirement: Simulation requirement text
            entity_type: Optional filter for entity type
            max_agents: Maximum number of agents to generate
            callback: Progress callback(progress: int)

        Returns:
            List of agent profile dicts
        """
        entities = self.entity_reader.get_entities(graph_id, entity_type)

        if max_agents and len(entities) > max_agents:
            entities = entities[:max_agents]

        profiles = []
        total = len(entities)

        for i, entity in enumerate(entities):
            try:
                profile = self.generate_profile(entity, requirement)
                profiles.append(profile)
            except Exception as e:
                # Log error but continue with other entities
                fallback = dict(_PROFILE_DEFAULTS)
                fallback.update({
                    'agent_id': str(uuid.uuid4())[:8],
                    'name': entity.get('name', 'Unknown'),
                    'username': f"user_{uuid.uuid4().hex[:8]}",
                    'bio': f"Based on {entity.get('name', 'unknown entity')}",
                    'persona': entity.get('description', ''),
                    'source_entity_id': entity.get('id', ''),
                    'source_entity_name': entity.get('name', ''),
                    'source_entity_type': entity.get('type', ''),
                    'created_at': datetime.now().isoformat(),
                    'error': str(e),
                })
                profiles.append(fallback)

            if callback:
                callback(int((i + 1) / total * 100))

        return profiles

    def save_profiles(self, simulation_id: str, profiles: list[dict]) -> str:
        """Save profiles to JSON file.

        Args:
            simulation_id: Simulation identifier
            profiles: List of profile dicts

        Returns:
            Path to saved file
        """
        sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
        os.makedirs(sim_dir, exist_ok=True)

        path = os.path.join(sim_dir, 'profiles.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

        return path

    def load_profiles(self, simulation_id: str) -> list[dict]:
        """Load profiles from JSON file."""
        path = os.path.join(
            Config.DATA_DIR, 'simulations', simulation_id, 'profiles.json'
        )
        if not os.path.exists(path):
            raise FileNotFoundError(f"Profiles not found for simulation {simulation_id}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _build_entity_context(self, entity: dict) -> str:
        """Build a text context string from entity data."""
        parts = [
            f"Name: {entity.get('name', 'Unknown')}",
            f"Type: {entity.get('type', 'Unknown')}",
            f"Description: {entity.get('description', 'N/A')}",
        ]

        # Summary (if available)
        summary = entity.get('summary', '')
        if summary:
            parts.append(f"Summary: {summary}")

        # Attributes
        attrs = entity.get('attributes', {})
        if attrs:
            attr_lines = [f"  - {k}: {v}" for k, v in attrs.items()]
            parts.append("Attributes:\n" + "\n".join(attr_lines))

        # Edges / relationships
        edges = entity.get('edges', [])
        if edges:
            edge_lines = []
            for edge in edges[:10]:  # Limit to avoid token overflow
                if edge.get('direction') == 'outgoing':
                    edge_lines.append(
                        f"  - {edge.get('relation', '?')} -> {edge.get('target_name', '?')}: {edge.get('fact', '')}"
                    )
                else:
                    edge_lines.append(
                        f"  - {edge.get('source_name', '?')} {edge.get('relation', '?')} -> this entity: {edge.get('fact', '')}"
                    )
            parts.append("Relationships:\n" + "\n".join(edge_lines))

        # Neighbors
        neighbors = entity.get('neighbors', [])
        if neighbors:
            neighbor_names = [
                f"{n.get('name', '?')} ({n.get('type', '?')})"
                for n in neighbors[:10]
            ]
            parts.append(f"Connected entities: {', '.join(neighbor_names)}")

        return "\n".join(parts)
