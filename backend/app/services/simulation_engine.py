"""Custom multi-agent social simulation engine replacing OASIS."""

import json
import os
import random
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

from app.config import Config
from app.utils.llm_client import LLMClient


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Post:
    id: str
    agent_id: str
    agent_name: str
    content: str
    platform: str  # twitter / reddit
    timestamp: str
    round_num: int
    likes: int = 0
    reposts: int = 0
    comments: list = field(default_factory=list)
    # reddit-specific
    upvotes: int = 0
    downvotes: int = 0
    # twitter-specific
    quote_of: str = ''   # id of quoted post
    repost_of: str = ''  # id of reposted post

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Action:
    id: str
    agent_id: str
    agent_name: str
    action_type: str
    platform: str
    round_num: int
    timestamp: str
    content: str = ''
    target_post_id: str = ''
    result_post_id: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SimulationState:
    simulation_id: str
    status: str = 'created'  # created/preparing/ready/running/completed/stopped/failed
    current_round: int = 0
    max_rounds: int = 10
    twitter_posts: list = field(default_factory=list)   # list of Post dicts
    reddit_posts: list = field(default_factory=list)     # list of Post dicts
    actions: list = field(default_factory=list)           # list of Action dicts
    agents: dict = field(default_factory=dict)            # agent_id -> profile
    started_at: str = ''
    completed_at: str = ''
    error: str = ''

    def to_dict(self) -> dict:
        return {
            'simulation_id': self.simulation_id,
            'status': self.status,
            'current_round': self.current_round,
            'max_rounds': self.max_rounds,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'error': self.error,
            'total_posts': len(self.twitter_posts) + len(self.reddit_posts),
            'total_actions': len(self.actions),
            'agent_count': len(self.agents),
        }

    def to_detail_dict(self, recent_n: int = 20) -> dict:
        d = self.to_dict()
        d['recent_actions'] = [
            a if isinstance(a, dict) else a.to_dict()
            for a in self.actions[-recent_n:]
        ]
        return d


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SimulationEngine:
    """Multi-agent social simulation engine."""

    MAX_FEED_SIZE = 15
    POPULARITY_NORMALIZER = 10.0

    def __init__(
        self,
        simulation_id: str,
        profiles: list[dict],
        config: dict,
        llm_client: LLMClient = None,
    ):
        self.llm = llm_client or LLMClient()
        self.simulation_id = simulation_id

        # Parse config
        time_cfg = config.get('time', {})
        self.minutes_per_round = time_cfg.get('minutes_per_round', 60)
        total_hours = time_cfg.get('total_simulation_hours', 72)
        max_rounds_cfg = (total_hours * 60) // self.minutes_per_round

        self.state = SimulationState(
            simulation_id=simulation_id,
            max_rounds=min(max_rounds_cfg, Config.OASIS_DEFAULT_MAX_ROUNDS * 100),
        )

        # Register agents
        for p in profiles:
            aid = p.get('agent_id', str(uuid.uuid4())[:8])
            self.state.agents[aid] = p

        # Config
        self.config = config
        self.agent_configs = {
            a['agent_id']: a for a in config.get('agents', [])
        }
        self.platform_config = config.get('platform', {
            'recency_weight': 0.4,
            'popularity_weight': 0.3,
            'relevance_weight': 0.3,
        })
        self.events = config.get('events', {})

        # Control
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially

        # Actions log file
        self._actions_path = os.path.join(
            Config.DATA_DIR, 'simulations', simulation_id, 'actions.jsonl'
        )
        os.makedirs(os.path.dirname(self._actions_path), exist_ok=True)

    # ----- lifecycle -----

    def start(self):
        """Start simulation in background thread."""
        if self.state.status == 'running':
            return
        self.state.status = 'running'
        self.state.started_at = datetime.now().isoformat()
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop simulation."""
        self.state.status = 'stopped'
        self.state.completed_at = datetime.now().isoformat()
        self._stop_event.set()
        self._pause_event.set()  # unpause so thread can exit

    def pause(self):
        """Pause simulation."""
        self._pause_event.clear()
        self.state.status = 'paused'

    def resume(self):
        """Resume paused simulation."""
        self._pause_event.set()
        self.state.status = 'running'

    def get_status(self) -> dict:
        return self.state.to_dict()

    def get_detail_status(self) -> dict:
        return self.state.to_detail_dict()

    def get_timeline(self) -> list[dict]:
        """Get posts grouped by round."""
        rounds: dict[int, list] = {}
        all_posts = self.state.twitter_posts + self.state.reddit_posts
        for p in all_posts:
            r = p.get('round_num', 0) if isinstance(p, dict) else p.round_num
            rounds.setdefault(r, []).append(
                p if isinstance(p, dict) else p.to_dict()
            )
        return [
            {'round': r, 'posts': posts}
            for r, posts in sorted(rounds.items())
        ]

    def get_actions(self, offset: int = 0, limit: int = 50) -> list[dict]:
        """Get paginated action history."""
        actions = self.state.actions[offset:offset + limit]
        return [a if isinstance(a, dict) else a.to_dict() for a in actions]

    def get_agent_stats(self) -> list[dict]:
        """Per-agent statistics."""
        stats: dict[str, dict] = {}
        for aid, profile in self.state.agents.items():
            stats[aid] = {
                'agent_id': aid,
                'agent_name': profile.get('name', ''),
                'total_actions': 0,
                'posts_created': 0,
                'comments_created': 0,
                'likes_given': 0,
                'reposts': 0,
                'do_nothing': 0,
            }

        for action in self.state.actions:
            a = action if isinstance(action, dict) else action.to_dict()
            aid = a.get('agent_id', '')
            if aid not in stats:
                continue
            stats[aid]['total_actions'] += 1
            atype = a.get('action_type', '')
            if atype in ('CREATE_POST',):
                stats[aid]['posts_created'] += 1
            elif atype in ('CREATE_COMMENT',):
                stats[aid]['comments_created'] += 1
            elif atype in ('LIKE_POST', 'UPVOTE_POST'):
                stats[aid]['likes_given'] += 1
            elif atype in ('REPOST', 'QUOTE_POST'):
                stats[aid]['reposts'] += 1
            elif atype == 'DO_NOTHING':
                stats[aid]['do_nothing'] += 1

        return list(stats.values())

    # ----- internal loop -----

    def _run_loop(self):
        """Main simulation loop."""
        try:
            # Seed initial posts from config
            self._seed_initial_posts()

            while self.state.current_round < self.state.max_rounds:
                # Check stop
                if self._stop_event.is_set():
                    break

                # Wait if paused
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                self.state.current_round += 1
                self._run_round(self.state.current_round)

            if not self._stop_event.is_set():
                self.state.status = 'completed'
                self.state.completed_at = datetime.now().isoformat()

        except Exception as e:
            if not self._stop_event.is_set():
                self.state.status = 'failed'
                self.state.error = str(e)
                self.state.completed_at = datetime.now().isoformat()

    def _seed_initial_posts(self):
        """Create initial posts from event config."""
        initial_posts = self.events.get('initial_posts', [])
        for ip in initial_posts:
            agent_name = ip.get('agent_name', '')
            content = ip.get('content', '')
            platform = ip.get('platform', 'twitter')

            # Find agent by name
            agent_id = self._find_agent_by_name(agent_name)
            if not agent_id:
                # Use first agent as fallback
                agent_id = next(iter(self.state.agents), '')
                agent_name = self.state.agents.get(agent_id, {}).get('name', agent_name)

            post = Post(
                id=str(uuid.uuid4())[:8],
                agent_id=agent_id,
                agent_name=agent_name,
                content=content,
                platform=platform,
                timestamp=datetime.now().isoformat(),
                round_num=0,
            )
            self._add_post(post)

            action = Action(
                id=str(uuid.uuid4())[:8],
                agent_id=agent_id,
                agent_name=agent_name,
                action_type='CREATE_POST',
                platform=platform,
                round_num=0,
                timestamp=post.timestamp,
                content=content,
                result_post_id=post.id,
            )
            self._log_action(action)

    def _run_round(self, round_num: int):
        """Execute one simulation round."""
        active_agents = self._select_active_agents(round_num)

        for agent_id in active_agents:
            if self._stop_event.is_set():
                break
            self._process_agent_turn(agent_id, round_num)

    def _process_agent_turn(self, agent_id: str, round_num: int):
        """Process a single agent's turn: build feed, decide, execute."""
        profile = self.state.agents.get(agent_id, {})
        platform = random.choice(['twitter', 'reddit'])

        feed = self._build_feed(agent_id, platform)

        if platform == 'twitter':
            action_list = Config.TWITTER_ACTIONS
        else:
            action_list = Config.REDDIT_ACTIONS

        decision = self._get_agent_decision(
            profile, feed, action_list, platform, round_num
        )

        self._execute_decision(
            agent_id, profile, decision, platform, round_num
        )

    def _select_active_agents(self, round_num: int) -> list[str]:
        """Select which agents are active this round based on activity config."""
        active = []
        for aid, profile in self.state.agents.items():
            agent_cfg = self.agent_configs.get(aid, {})
            activity = agent_cfg.get(
                'activity_level', profile.get('activity_level', 'medium')
            )
            pph = agent_cfg.get('posts_per_hour', 0.5)

            # Probability of being active this round
            hours_per_round = self.minutes_per_round / 60.0
            probability = min(pph * hours_per_round, 1.0)

            # Adjust by activity level
            multipliers = {'low': 0.5, 'medium': 1.0, 'high': 1.5}
            probability *= multipliers.get(activity, 1.0)
            probability = min(probability, 1.0)

            if random.random() < probability:
                active.append(aid)

        # Shuffle order
        random.shuffle(active)
        return active

    def _score_post(
        self,
        post_dict: dict,
        agent_topics: list[str],
        total_posts: int,
        post_index: int,
    ) -> float:
        """Score a single post by recency + popularity + relevance."""
        recency = (post_index + 1) / total_posts
        score = recency * self.platform_config.get('recency_weight', 0.4)

        popularity = (
            post_dict.get('likes', 0)
            + post_dict.get('reposts', 0)
            + post_dict.get('upvotes', 0)
            + len(post_dict.get('comments', []))
        )
        pop_score = min(popularity / self.POPULARITY_NORMALIZER, 1.0)
        score += pop_score * self.platform_config.get('popularity_weight', 0.3)

        content_lower = post_dict.get('content', '').lower()
        topic_matches = sum(
            1 for t in agent_topics if t.lower() in content_lower
        )
        rel_score = min(topic_matches / max(len(agent_topics), 1), 1.0)
        score += rel_score * self.platform_config.get('relevance_weight', 0.3)

        return score

    def _build_feed(self, agent_id: str, platform: str) -> list[dict]:
        """Build agent's feed from recent relevant posts."""
        posts = self._get_platform_posts(platform)
        if not posts:
            return []

        profile = self.state.agents.get(agent_id, {})
        topics = profile.get('interested_topics', [])
        total = len(posts)

        scored = []
        for idx, p in enumerate(posts):
            pd = p if isinstance(p, dict) else p.to_dict()
            if pd.get('agent_id') == agent_id:
                continue
            score = self._score_post(pd, topics, total, idx)
            scored.append((score, pd))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:self.MAX_FEED_SIZE]]

    def _get_agent_decision(
        self,
        profile: dict,
        feed: list[dict],
        action_list: list[str],
        platform: str,
        round_num: int,
    ) -> dict:
        """Ask LLM what action the agent should take."""
        agent_name = profile.get('name', 'Unknown')
        agent_bio = profile.get('bio', '')
        agent_persona = profile.get('persona', '')
        stance = profile.get('stance', 'neutral')
        topics = ', '.join(profile.get('interested_topics', []))

        # Build feed summary
        if feed:
            feed_lines = []
            for p in feed:
                comments_count = len(p.get('comments', []))
                likes = p.get('likes', 0) + p.get('upvotes', 0)
                feed_lines.append(
                    f"[Post {p.get('id', '?')}] by @{p.get('agent_name', '?')} "
                    f"({likes} likes, {comments_count} comments): "
                    f"{p.get('content', '')[:200]}"
                )
            feed_summary = "\n".join(feed_lines)
        else:
            feed_summary = "(No posts in feed yet - you could start the conversation!)"

        action_str = ', '.join(action_list)

        prompt = f"""You are {agent_name}, {agent_bio}.
Personality: {agent_persona}
Your stance: {stance}
Topics you care about: {topics}

Current social media feed ({platform}, round {round_num}):
{feed_summary}

Available actions: {action_str}

Based on your personality and the current discussion, decide what to do.
Return JSON: {{"action": "ACTION_TYPE", "content": "your post/comment text if applicable", "target_post_id": "id if replying/liking/reposting"}}

Rules:
- If creating a post/comment, write realistic content in character (max 280 chars for twitter, max 1000 for reddit)
- target_post_id is required for LIKE_POST, REPOST, QUOTE_POST, CREATE_COMMENT, UPVOTE_POST, DOWNVOTE_POST
- For CREATE_POST, content is required, target_post_id can be empty
- For DO_NOTHING, both content and target_post_id can be empty
- Stay in character!

Return ONLY the JSON object."""

        result = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.9,
        )

        # Validate action type
        action_type = result.get('action', 'DO_NOTHING')
        if action_type not in action_list:
            action_type = 'DO_NOTHING'
        result['action'] = action_type

        return result

    def _execute_decision(
        self,
        agent_id: str,
        profile: dict,
        decision: dict,
        platform: str,
        round_num: int,
    ):
        """Execute an agent's decision."""
        action_type = decision.get('action', 'DO_NOTHING')
        content = decision.get('content', '')
        target_id = decision.get('target_post_id', '')
        agent_name = profile.get('name', '')
        timestamp = datetime.now().isoformat()

        result_post_id = ''

        if action_type == 'CREATE_POST':
            post = Post(
                id=str(uuid.uuid4())[:8],
                agent_id=agent_id,
                agent_name=agent_name,
                content=content,
                platform=platform,
                timestamp=timestamp,
                round_num=round_num,
            )
            self._add_post(post)
            result_post_id = post.id

        elif action_type == 'LIKE_POST':
            self._apply_to_post(target_id, platform, lambda p: _inc(p, 'likes'))

        elif action_type == 'UPVOTE_POST':
            self._apply_to_post(target_id, platform, lambda p: _inc(p, 'upvotes'))

        elif action_type == 'DOWNVOTE_POST':
            self._apply_to_post(target_id, platform, lambda p: _inc(p, 'downvotes'))

        elif action_type == 'REPOST':
            post = Post(
                id=str(uuid.uuid4())[:8],
                agent_id=agent_id,
                agent_name=agent_name,
                content=content or f"RT: {self._get_post_content(target_id, platform)}",
                platform=platform,
                timestamp=timestamp,
                round_num=round_num,
                repost_of=target_id,
            )
            self._add_post(post)
            self._apply_to_post(target_id, platform, lambda p: _inc(p, 'reposts'))
            result_post_id = post.id

        elif action_type == 'QUOTE_POST':
            post = Post(
                id=str(uuid.uuid4())[:8],
                agent_id=agent_id,
                agent_name=agent_name,
                content=content,
                platform=platform,
                timestamp=timestamp,
                round_num=round_num,
                quote_of=target_id,
            )
            self._add_post(post)
            result_post_id = post.id

        elif action_type == 'CREATE_COMMENT':
            comment = {
                'id': str(uuid.uuid4())[:8],
                'agent_id': agent_id,
                'agent_name': agent_name,
                'content': content,
                'timestamp': timestamp,
                'round_num': round_num,
            }
            self._add_comment(target_id, platform, comment)

        # Log action
        action = Action(
            id=str(uuid.uuid4())[:8],
            agent_id=agent_id,
            agent_name=agent_name,
            action_type=action_type,
            platform=platform,
            round_num=round_num,
            timestamp=timestamp,
            content=content,
            target_post_id=target_id,
            result_post_id=result_post_id,
        )
        self._log_action(action)

    # ----- helpers -----

    def _get_platform_posts(self, platform: str) -> list:
        """Return the post list for the given platform."""
        if platform == 'twitter':
            return self.state.twitter_posts
        return self.state.reddit_posts

    def _find_post(self, post_id: str, platform: str):
        """Find a post by id in the given platform. Returns the post dict/object or None."""
        for p in self._get_platform_posts(platform):
            pid = p.get('id') if isinstance(p, dict) else p.id
            if pid == post_id:
                return p
        return None

    def _add_post(self, post: Post):
        """Add post to appropriate platform list."""
        self._get_platform_posts(post.platform).append(post.to_dict())

    def _apply_to_post(self, post_id: str, platform: str, fn):
        """Apply a function to a post found by id."""
        post = self._find_post(post_id, platform)
        if post is not None:
            fn(post)

    def _add_comment(self, post_id: str, platform: str, comment: dict):
        """Add comment to a post."""
        post = self._find_post(post_id, platform)
        if post is None:
            return
        if isinstance(post, dict):
            post.setdefault('comments', []).append(comment)
        else:
            post.comments.append(comment)

    def _get_post_content(self, post_id: str, platform: str) -> str:
        """Get content of a post by id."""
        post = self._find_post(post_id, platform)
        if post is None:
            return ''
        if isinstance(post, dict):
            return post.get('content', '')
        return post.content

    def _find_agent_by_name(self, name: str) -> str:
        """Find agent_id by name (case-insensitive)."""
        name_lower = name.lower()
        for aid, profile in self.state.agents.items():
            if profile.get('name', '').lower() == name_lower:
                return aid
        return ''

    def _log_action(self, action: Action):
        """Log action to state and to JSONL file."""
        ad = action.to_dict()
        self.state.actions.append(ad)

        try:
            with open(self._actions_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(ad, ensure_ascii=False) + '\n')
        except Exception:
            pass  # Non-critical — state still has the action


def _inc(post, field_name: str):
    """Increment a numeric field on a post dict."""
    if isinstance(post, dict):
        post[field_name] = post.get(field_name, 0) + 1
    else:
        setattr(post, field_name, getattr(post, field_name, 0) + 1)
