"""Generate simulation configuration using LLM with step-by-step generation."""

import json
import math
import os
from dataclasses import dataclass, field, asdict

from app.config import Config
from app.utils.llm_client import LLMClient


@dataclass
class TimeConfig:
    total_simulation_hours: int = 72
    minutes_per_round: int = 60
    peak_hours: list = field(default_factory=lambda: [19, 20, 21, 22])
    off_peak_hours: list = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    peak_multiplier: float = 1.5
    off_peak_multiplier: float = 0.3

    @property
    def total_rounds(self) -> int:
        return (self.total_simulation_hours * 60) // self.minutes_per_round


@dataclass
class EventConfig:
    initial_posts: list = field(default_factory=list)
    hot_topics: list = field(default_factory=list)
    narrative_direction: str = ''


@dataclass
class AgentConfig:
    agent_id: str = ''
    agent_name: str = ''
    activity_level: str = 'medium'  # low/medium/high
    posts_per_hour: float = 0.5
    comments_per_hour: float = 1.0
    active_hours: list = field(default_factory=lambda: list(range(8, 24)))
    response_delay: int = 15  # minutes
    influence_weight: float = 0.5  # 0-1
    sentiment_bias: float = 0.0  # -1.0 negative to 1.0 positive
    stance: str = 'neutral'


@dataclass
class PlatformConfig:
    recency_weight: float = 0.4
    popularity_weight: float = 0.3
    relevance_weight: float = 0.3


@dataclass
class SimulationConfig:
    time: TimeConfig = field(default_factory=TimeConfig)
    events: EventConfig = field(default_factory=EventConfig)
    agents: list = field(default_factory=list)  # list of AgentConfig dicts
    platform: PlatformConfig = field(default_factory=PlatformConfig)

    def to_dict(self) -> dict:
        return {
            'time': asdict(self.time),
            'events': asdict(self.events),
            'agents': self.agents,
            'platform': asdict(self.platform),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SimulationConfig':
        config = cls()
        if 'time' in data:
            config.time = TimeConfig(**{
                k: v for k, v in data['time'].items()
                if k != 'total_rounds'
            })
        if 'events' in data:
            config.events = EventConfig(**data['events'])
        if 'agents' in data:
            config.agents = data['agents']
        if 'platform' in data:
            config.platform = PlatformConfig(**data['platform'])
        return config


class SimulationConfigGenerator:
    """Generate simulation configuration using LLM in structured steps."""

    AGENT_BATCH_SIZE = 15

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    def generate(
        self,
        profiles: list[dict],
        requirement: str = '',
        max_rounds: int = None,
    ) -> SimulationConfig:
        """Generate full simulation config from agent profiles and requirement.

        Uses step-by-step generation for deeper, more coherent configs:
          Step 1: Time config
          Step 2: Event config
          Step 3: Agent configs (batched, 15 per batch)
          Step 4: Platform config

        Args:
            profiles: List of agent profile dicts
            requirement: Simulation requirement text
            max_rounds: Override for max rounds (if None, LLM decides)

        Returns:
            SimulationConfig instance
        """
        agent_summary = self._build_agent_summary(profiles)
        scenario = requirement or (
            'General social media simulation about the topics these agents '
            'care about'
        )

        # Step 1: Time config
        time_config = self._generate_time_config(agent_summary, scenario)

        # Step 2: Event config
        event_config = self._generate_event_config(
            agent_summary, scenario, time_config
        )

        # Step 3: Agent configs (batched)
        agent_configs = self._generate_agent_configs(
            profiles, agent_summary, scenario, event_config
        )

        # Step 4: Platform config
        platform_config = self._generate_platform_config(
            agent_summary, scenario, event_config
        )

        config = SimulationConfig(
            time=time_config,
            events=event_config,
            agents=agent_configs,
            platform=platform_config,
        )

        # Override max rounds if specified
        if max_rounds is not None:
            config.time.total_simulation_hours = (
                max_rounds * config.time.minutes_per_round
            ) // 60

        return config

    # ── Step 1: Time Config ──────────────────────────────────────────

    def _generate_time_config(
        self, agent_summary: str, scenario: str
    ) -> TimeConfig:
        """Generate time configuration based on scenario and agents."""
        prompt = f"""You are designing a social media simulation.

Scenario: {scenario}

Agents:
{agent_summary}

Generate the TIME configuration as JSON. Consider:
- How long should the simulation run to capture meaningful dynamics?
- What hours are peak engagement hours for these agents' demographics?
- What hours are off-peak (sleeping/inactive)?
- How much should activity multiply during peak vs off-peak?

Return JSON:
{{
  "total_simulation_hours": 72,
  "minutes_per_round": 60,
  "peak_hours": [19, 20, 21, 22],
  "off_peak_hours": [0, 1, 2, 3, 4, 5],
  "peak_multiplier": 1.5,
  "off_peak_multiplier": 0.3
}}

Rules:
- total_simulation_hours: 24-168 (1-7 days)
- minutes_per_round: 15, 30, or 60
- peak_hours: list of hours (0-23) when engagement is highest
- off_peak_hours: list of hours (0-23) when engagement is lowest
- peak_multiplier: 1.2-2.0 (how much more active during peak)
- off_peak_multiplier: 0.1-0.5 (how much less active during off-peak)

Return ONLY the JSON object."""

        result = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
        )

        return TimeConfig(
            total_simulation_hours=result.get('total_simulation_hours', 72),
            minutes_per_round=result.get('minutes_per_round', 60),
            peak_hours=result.get('peak_hours', [19, 20, 21, 22]),
            off_peak_hours=result.get('off_peak_hours', [0, 1, 2, 3, 4, 5]),
            peak_multiplier=max(1.0, min(
                2.0, result.get('peak_multiplier', 1.5)
            )),
            off_peak_multiplier=max(0.1, min(
                0.5, result.get('off_peak_multiplier', 0.3)
            )),
        )

    # ── Step 2: Event Config ─────────────────────────────────────────

    def _generate_event_config(
        self, agent_summary: str, scenario: str, time_config: TimeConfig
    ) -> EventConfig:
        """Generate event configuration with scenario-aware seeding."""
        prompt = f"""You are designing a social media simulation.

Scenario: {scenario}

Agents:
{agent_summary}

Simulation duration: {time_config.total_simulation_hours} hours, \
{time_config.minutes_per_round} min/round.

Generate the EVENT configuration as JSON. Consider:
- Which agents would naturally post first given their personality/activity?
- What initial posts would spark engagement from other agents?
- What topics are most likely to generate debate and interaction?
- How should the narrative arc evolve over {time_config.total_simulation_hours} hours?

Return JSON:
{{
  "initial_posts": [
    {{
      "agent_name": "who posts first",
      "content": "realistic opening post matching their voice",
      "platform": "twitter"
    }}
  ],
  "hot_topics": ["topic1", "topic2", "topic3"],
  "narrative_direction": "Detailed description of how the simulation evolves"
}}

Rules:
- Create 2-4 initial_posts that seed the conversation naturally
- Each initial_post content should match the posting agent's voice and stance
- hot_topics: 3-5 specific topics from the scenario domain
- narrative_direction: describe the expected arc (early debate, peak conflict, \
resolution/divergence)
- agent_name must exactly match one of the agents listed above

Return ONLY the JSON object."""

        result = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        return EventConfig(
            initial_posts=result.get('initial_posts', []),
            hot_topics=result.get('hot_topics', []),
            narrative_direction=result.get('narrative_direction', ''),
        )

    # ── Step 3: Agent Configs (batched) ──────────────────────────────

    def _generate_agent_configs(
        self,
        profiles: list[dict],
        agent_summary: str,
        scenario: str,
        event_config: EventConfig,
    ) -> list[dict]:
        """Generate per-agent configs in batches of AGENT_BATCH_SIZE."""
        all_agent_configs = []
        batch_count = math.ceil(len(profiles) / self.AGENT_BATCH_SIZE)

        for batch_idx in range(batch_count):
            start = batch_idx * self.AGENT_BATCH_SIZE
            end = start + self.AGENT_BATCH_SIZE
            batch_profiles = profiles[start:end]

            batch_configs = self._generate_agent_batch(
                batch_profiles, agent_summary, scenario, event_config
            )
            all_agent_configs.extend(batch_configs)

        return all_agent_configs

    def _generate_agent_batch(
        self,
        batch_profiles: list[dict],
        agent_summary: str,
        scenario: str,
        event_config: EventConfig,
    ) -> list[dict]:
        """Generate configs for a batch of agents."""
        batch_detail = self._build_batch_detail(batch_profiles)
        topics_str = ', '.join(event_config.hot_topics[:5])

        prompt = f"""You are configuring agents for a social media simulation.

Scenario: {scenario}
Hot topics: {topics_str}
Narrative: {event_config.narrative_direction}

Agents to configure (with their profiles):
{batch_detail}

Generate a configuration for EACH agent as a JSON array. Consider:
- Their profession and interests determine active_hours and posting patterns
- Their stance and personality determine sentiment_bias and influence_weight
- Realistic social media behavior: most people comment MORE than they post
- Response delay varies: impulsive users respond fast, thoughtful ones slower
- Influence weight reflects their authority/reach in the simulation domain

Return JSON array:
[
  {{
    "agent_id": "the agent's id",
    "agent_name": "the agent's name",
    "activity_level": "low/medium/high",
    "posts_per_hour": 0.5,
    "comments_per_hour": 1.5,
    "active_hours": [9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21],
    "response_delay": 15,
    "influence_weight": 0.5,
    "sentiment_bias": 0.0,
    "stance": "their stance on the topic"
  }}
]

Rules:
- activity_level: low=0.1-0.3 posts/hr, medium=0.3-0.7, high=0.7-1.5
- comments_per_hour: typically 1.5-3x posts_per_hour
- active_hours: list of hours (0-23) when this agent is online
  - professionals: mostly business hours + evenings
  - students/young: late morning through late night
  - retirees: morning through early evening
- response_delay: 1-60 minutes (impulsive=1-5, normal=10-20, thoughtful=30-60)
- influence_weight: 0.0-1.0 (expert in topic=0.7-1.0, casual=0.2-0.4)
- sentiment_bias: -1.0 (very negative) to 1.0 (very positive)
- Every agent in the list above MUST appear in the output

Return ONLY the JSON array."""

        result = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.6,
        )

        # Result could be a list (if LLM returns array) or dict with agents key
        if isinstance(result, list):
            raw_agents = result
        else:
            raw_agents = result.get('agents', result.get('data', []))
            if not isinstance(raw_agents, list):
                raw_agents = []

        return self._reconcile_agent_batch(batch_profiles, raw_agents)

    def _reconcile_agent_batch(
        self, profiles: list[dict], raw_agents: list[dict]
    ) -> list[dict]:
        """Ensure every profile has a config, filling gaps with defaults."""
        agent_map = {a.get('agent_id'): a for a in raw_agents}
        agent_name_map = {
            a.get('agent_name', '').lower(): a for a in raw_agents
        }

        configs = []
        for profile in profiles:
            aid = profile.get('agent_id', '')
            aname = profile.get('name', '')

            matched = (
                agent_map.get(aid)
                or agent_name_map.get(aname.lower(), {})
            )

            activity = matched.get(
                'activity_level', profile.get('activity_level', 'medium')
            )
            pph_defaults = {'low': 0.2, 'medium': 0.5, 'high': 1.0}
            cph_defaults = {'low': 0.5, 'medium': 1.0, 'high': 2.0}

            configs.append({
                'agent_id': aid,
                'agent_name': aname,
                'activity_level': activity,
                'posts_per_hour': matched.get(
                    'posts_per_hour', pph_defaults.get(activity, 0.5)
                ),
                'comments_per_hour': matched.get(
                    'comments_per_hour', cph_defaults.get(activity, 1.0)
                ),
                'active_hours': matched.get(
                    'active_hours', list(range(8, 24))
                ),
                'response_delay': max(1, min(
                    60, matched.get('response_delay', 15)
                )),
                'influence_weight': max(0.0, min(
                    1.0, matched.get('influence_weight', 0.5)
                )),
                'sentiment_bias': max(-1.0, min(
                    1.0, matched.get('sentiment_bias', 0.0)
                )),
                'stance': matched.get(
                    'stance', profile.get('stance', 'neutral')
                ),
            })

        return configs

    # ── Step 4: Platform Config ──────────────────────────────────────

    def _generate_platform_config(
        self, agent_summary: str, scenario: str, event_config: EventConfig
    ) -> PlatformConfig:
        """Generate platform feed algorithm weights."""
        topics_str = ', '.join(event_config.hot_topics[:5])

        prompt = f"""You are configuring the feed algorithm for a social media \
simulation.

Scenario: {scenario}
Hot topics: {topics_str}

Generate platform configuration as JSON. Consider:
- Should recent posts be prioritized (breaking news scenario) or popular ones \
(viral content)?
- How important is topic relevance for this scenario?

Return JSON:
{{
  "recency_weight": 0.4,
  "popularity_weight": 0.3,
  "relevance_weight": 0.3
}}

Rules:
- All three weights must sum to 1.0
- Each weight: 0.1-0.6
- Breaking news scenarios: higher recency_weight
- Viral/engagement scenarios: higher popularity_weight
- Niche/expert scenarios: higher relevance_weight

Return ONLY the JSON object."""

        result = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        recency = result.get('recency_weight', 0.4)
        popularity = result.get('popularity_weight', 0.3)
        relevance = result.get('relevance_weight', 0.3)

        # Normalize to sum to 1.0
        total = recency + popularity + relevance
        if total > 0:
            recency /= total
            popularity /= total
            relevance /= total

        return PlatformConfig(
            recency_weight=round(recency, 2),
            popularity_weight=round(popularity, 2),
            relevance_weight=round(relevance, 2),
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def save_config(self, simulation_id: str, config: SimulationConfig) -> str:
        """Save config to JSON file."""
        sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
        os.makedirs(sim_dir, exist_ok=True)

        path = os.path.join(sim_dir, 'config.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_config(self, simulation_id: str) -> SimulationConfig:
        """Load config from JSON file."""
        path = os.path.join(
            Config.DATA_DIR, 'simulations', simulation_id, 'config.json'
        )
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Config not found for simulation {simulation_id}"
            )
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return SimulationConfig.from_dict(data)

    def _build_agent_summary(self, profiles: list[dict]) -> str:
        """Build concise agent summary for LLM prompt."""
        lines = []
        for p in profiles:
            topics = ', '.join(p.get('interested_topics', [])[:5])
            lines.append(
                f"- {p.get('name', '?')} (id: {p.get('agent_id', '?')}): "
                f"{p.get('profession', '?')}, age {p.get('age', '?')}, "
                f"stance: {p.get('stance', '?')}, "
                f"activity: {p.get('activity_level', 'medium')}, "
                f"topics: [{topics}]"
            )
        return "\n".join(lines)

    def _build_batch_detail(self, profiles: list[dict]) -> str:
        """Build detailed agent descriptions for batch config generation."""
        lines = []
        for p in profiles:
            topics = ', '.join(p.get('interested_topics', [])[:5])
            personality = p.get('personality', '')
            bio = p.get('bio', p.get('description', ''))

            detail = (
                f"- {p.get('name', '?')} (id: {p.get('agent_id', '?')}):\n"
                f"  Profession: {p.get('profession', '?')}\n"
                f"  Age: {p.get('age', '?')}\n"
                f"  Stance: {p.get('stance', 'neutral')}\n"
                f"  Activity level: {p.get('activity_level', 'medium')}\n"
                f"  Topics: [{topics}]"
            )
            if personality:
                detail += f"\n  Personality: {personality}"
            if bio:
                detail += f"\n  Bio: {bio[:150]}"
            lines.append(detail)

        return "\n".join(lines)
