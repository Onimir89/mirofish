"""Orchestrates simulation preparation and execution."""

import json
import os
import threading
import uuid
from datetime import datetime

from app.config import Config
from app.utils.llm_client import LLMClient
from app.models.project import Project
from app.services.profile_generator import ProfileGenerator
from app.services.simulation_config_generator import SimulationConfigGenerator
from app.services.simulation_engine import SimulationEngine


class SimulationManager:
    """Manages the full simulation lifecycle.

    States: CREATED -> PREPARING -> READY -> RUNNING -> COMPLETED/STOPPED/FAILED
    """

    # In-memory registry of all simulations
    _simulations: dict[str, dict] = {}
    _engines: dict[str, SimulationEngine] = {}
    _prep_threads: dict[str, threading.Thread] = {}
    _lock = threading.RLock()

    @classmethod
    def create_simulation(
        cls,
        project_id: str,
        name: str = '',
        max_rounds: int = None,
        max_agents: int = None,
    ) -> dict:
        """Create a new simulation record.

        Args:
            project_id: Project with knowledge graph
            name: Simulation name
            max_rounds: Override max rounds
            max_agents: Max number of agents to generate

        Returns:
            Simulation metadata dict
        """
        # Validate project exists and has a graph
        project = Project.load(project_id)
        if not project.graph_id:
            raise ValueError("Project does not have a built knowledge graph")

        sim_id = str(uuid.uuid4())[:12]
        sim = {
            'id': sim_id,
            'name': name or f"Simulation {sim_id}",
            'project_id': project_id,
            'graph_id': project.graph_id,
            'status': 'created',
            'max_rounds': max_rounds or Config.OASIS_DEFAULT_MAX_ROUNDS,
            'max_agents': max_agents,
            'created_at': datetime.now().isoformat(),
            'profiles': [],
            'config': {},
            'prep_progress': 0,
            'prep_error': '',
        }

        with cls._lock:
            cls._simulations[sim_id] = sim
        cls._save_simulation(sim_id)

        return sim

    @classmethod
    def prepare_simulation(cls, simulation_id: str) -> dict:
        """Prepare simulation: generate profiles + config (async).

        Returns:
            Updated simulation metadata
        """
        sim = cls._get_simulation(simulation_id)
        if sim['status'] not in ('created', 'failed'):
            raise ValueError(
                f"Cannot prepare simulation in status '{sim['status']}'"
            )

        sim['status'] = 'preparing'
        sim['prep_progress'] = 0
        sim['prep_error'] = ''
        cls._save_simulation(simulation_id)

        def _prepare():
            try:
                llm = LLMClient()
                project = Project.load(sim['project_id'])

                # Step 1: Generate profiles (0-60%)
                profile_gen = ProfileGenerator(llm)

                def profile_cb(progress):
                    sim['prep_progress'] = int(progress * 0.6)

                profiles = profile_gen.generate_profiles_batch(
                    graph_id=sim['graph_id'],
                    requirement=project.simulation_requirement,
                    max_agents=sim.get('max_agents'),
                    callback=profile_cb,
                )
                profile_gen.save_profiles(simulation_id, profiles)
                sim['profiles'] = profiles
                sim['prep_progress'] = 60

                # Step 2: Generate config (60-90%)
                config_gen = SimulationConfigGenerator(llm)
                config = config_gen.generate(
                    profiles=profiles,
                    requirement=project.simulation_requirement,
                    max_rounds=sim.get('max_rounds'),
                )
                config_gen.save_config(simulation_id, config)
                sim['config'] = config.to_dict()
                sim['prep_progress'] = 90

                # Step 3: Finalize (90-100%)
                sim['status'] = 'ready'
                sim['prep_progress'] = 100
                cls._save_simulation(simulation_id)

            except Exception as e:
                sim['status'] = 'failed'
                sim['prep_error'] = str(e)
                cls._save_simulation(simulation_id)

        thread = threading.Thread(target=_prepare, daemon=True)
        with cls._lock:
            cls._prep_threads[simulation_id] = thread
        thread.start()

        return sim

    @classmethod
    def start_simulation(cls, simulation_id: str) -> dict:
        """Start simulation engine in background.

        Returns:
            Updated simulation metadata
        """
        sim = cls._get_simulation(simulation_id)
        if sim['status'] != 'ready':
            raise ValueError(
                f"Cannot start simulation in status '{sim['status']}'. "
                "Must be 'ready' first."
            )

        profiles = sim.get('profiles', [])
        config = sim.get('config', {})

        if not profiles:
            raise ValueError("No profiles generated. Run prepare first.")

        # Create engine
        engine = SimulationEngine(
            simulation_id=simulation_id,
            profiles=profiles,
            config=config,
        )
        with cls._lock:
            cls._engines[simulation_id] = engine

        # Start
        engine.start()
        sim['status'] = 'running'
        cls._save_simulation(simulation_id)

        return sim

    @classmethod
    def stop_simulation(cls, simulation_id: str) -> dict:
        """Stop a running simulation."""
        sim = cls._get_simulation(simulation_id)
        with cls._lock:
            engine = cls._engines.get(simulation_id)
        if engine:
            engine.stop()
        sim['status'] = 'stopped'
        cls._save_simulation(simulation_id)
        return sim

    @classmethod
    def get_simulation(cls, simulation_id: str) -> dict:
        """Get simulation metadata."""
        return cls._get_simulation(simulation_id)

    @classmethod
    def get_status(cls, simulation_id: str) -> dict:
        """Get simulation run status (summary)."""
        return cls._get_engine_status(simulation_id, detailed=False)

    @classmethod
    def get_detail_status(cls, simulation_id: str) -> dict:
        """Get detailed status with recent actions."""
        return cls._get_engine_status(simulation_id, detailed=True)

    @classmethod
    def _get_engine_status(cls, simulation_id: str, detailed: bool) -> dict:
        """Get engine status, syncing state changes back to simulation metadata."""
        sim = cls._get_simulation(simulation_id)
        with cls._lock:
            engine = cls._engines.get(simulation_id)

        if engine:
            result = engine.get_detail_status() if detailed else engine.get_status()
            new_status = result.get('status', sim['status'])
            if new_status != sim['status']:
                sim['status'] = new_status
                if new_status in ('completed', 'stopped', 'failed'):
                    cls._save_simulation(simulation_id)
            return result

        fallback = {
            'simulation_id': simulation_id,
            'status': sim['status'],
            'current_round': 0,
            'max_rounds': sim.get('max_rounds', 0),
            'total_posts': 0,
            'total_actions': 0,
            'agent_count': len(sim.get('profiles', [])),
        }
        if detailed:
            fallback['recent_actions'] = []
        return fallback

    @classmethod
    def get_actions(
        cls, simulation_id: str, offset: int = 0, limit: int = 50
    ) -> list[dict]:
        """Get paginated action history."""
        with cls._lock:
            engine = cls._engines.get(simulation_id)
        if engine:
            return engine.get_actions(offset, limit)
        return []

    @classmethod
    def get_timeline(cls, simulation_id: str) -> list[dict]:
        """Get timeline grouped by rounds."""
        with cls._lock:
            engine = cls._engines.get(simulation_id)
        if engine:
            return engine.get_timeline()
        return []

    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> list[dict]:
        """Get per-agent statistics."""
        with cls._lock:
            engine = cls._engines.get(simulation_id)
        if engine:
            return engine.get_agent_stats()
        return []

    @classmethod
    def get_profiles(cls, simulation_id: str) -> list[dict]:
        """Get agent profiles."""
        sim = cls._get_simulation(simulation_id)
        return sim.get('profiles', [])

    @classmethod
    def get_config(cls, simulation_id: str) -> dict:
        """Get simulation config."""
        sim = cls._get_simulation(simulation_id)
        return sim.get('config', {})

    @classmethod
    def _get_platform_posts(cls, simulation_id: str, platform: str = None) -> list[dict] | None:
        """Get posts filtered by platform. Returns None if no engine."""
        with cls._lock:
            engine = cls._engines.get(simulation_id)
        if not engine:
            return None

        posts = []
        if platform in (None, 'twitter'):
            posts.extend(engine.state.twitter_posts)
        if platform in (None, 'reddit'):
            posts.extend(engine.state.reddit_posts)
        return posts

    @classmethod
    def get_posts(
        cls, simulation_id: str, platform: str = None,
        offset: int = 0, limit: int = 50,
    ) -> list[dict]:
        """Get posts from a simulation, optionally filtered by platform."""
        posts = cls._get_platform_posts(simulation_id, platform)
        if posts is None:
            return []

        posts.sort(key=lambda p: p.get('round_num', 0), reverse=True)
        return posts[offset:offset + limit]

    @classmethod
    def get_comments(
        cls, simulation_id: str, platform: str = None,
        offset: int = 0, limit: int = 50,
    ) -> list[dict]:
        """Get all comments from simulation posts, optionally filtered by platform."""
        sources = cls._get_platform_posts(simulation_id, platform)
        if sources is None:
            return []

        comments = []
        for post in sources:
            post_id = post.get('id', '')
            for c in post.get('comments', []):
                comment = dict(c)
                comment['post_id'] = post_id
                comment['platform'] = post.get('platform', '')
                comments.append(comment)

        comments.sort(key=lambda c: c.get('round_num', 0), reverse=True)
        return comments[offset:offset + limit]

    @classmethod
    def list_simulations_with_history(cls, limit: int = 20) -> list[dict]:
        """List simulations with run state info (recent actions, round progress)."""
        cls._load_all_from_disk()

        result = []
        with cls._lock:
            items = list(cls._simulations.items())

        for sid, sim in items:
            entry = cls._sim_summary(sim)
            entry.update({
                'current_round': 0,
                'total_posts': 0,
                'total_actions': 0,
                'recent_actions': [],
            })

            with cls._lock:
                engine = cls._engines.get(sid)
            if engine:
                status = engine.get_detail_status()
                entry['current_round'] = status.get('current_round', 0)
                entry['total_posts'] = status.get('total_posts', 0)
                entry['total_actions'] = status.get('total_actions', 0)
                entry['recent_actions'] = status.get('recent_actions', [])[:5]

            result.append(entry)

        result.sort(key=lambda s: s.get('created_at', ''), reverse=True)
        return result[:limit]

    @classmethod
    def get_prep_status(cls, simulation_id: str) -> dict:
        """Get preparation progress."""
        sim = cls._get_simulation(simulation_id)
        return {
            'simulation_id': simulation_id,
            'status': sim['status'],
            'progress': sim.get('prep_progress', 0),
            'error': sim.get('prep_error', ''),
        }

    @classmethod
    def list_simulations(cls) -> list[dict]:
        """List all simulations (from memory + disk)."""
        cls._load_all_from_disk()

        with cls._lock:
            items = list(cls._simulations.items())

        result = [cls._sim_summary(sim) for _, sim in items]
        result.sort(key=lambda s: s.get('created_at', ''), reverse=True)
        return result

    @classmethod
    def get_env_status(cls, simulation_id: str) -> dict:
        """Return whether the simulation engine is alive and resource usage.

        Returns:
            Dict with alive, status, agents count, posts count.
        """
        sim = cls._get_simulation(simulation_id)
        with cls._lock:
            engine = cls._engines.get(simulation_id)

        alive = engine is not None and engine._thread is not None and engine._thread.is_alive()
        agents = len(sim.get('profiles', []))
        posts = 0
        if engine:
            posts = len(engine.state.twitter_posts) + len(engine.state.reddit_posts)

        return {
            'simulation_id': simulation_id,
            'alive': alive,
            'status': sim['status'],
            'agents': agents,
            'posts': posts,
        }

    @classmethod
    def close_env(cls, simulation_id: str) -> dict:
        """Gracefully close a simulation environment.

        Stops the engine if running, removes it from _engines, and frees resources.

        Returns:
            Dict confirming closure.
        """
        sim = cls._get_simulation(simulation_id)
        with cls._lock:
            engine = cls._engines.pop(simulation_id, None)

        if engine:
            engine.stop()

        previous_status = sim['status']
        if sim['status'] == 'running':
            sim['status'] = 'stopped'
            cls._save_simulation(simulation_id)

        return {
            'simulation_id': simulation_id,
            'closed': True,
            'previous_status': previous_status,
        }

    # ----- internal -----

    @staticmethod
    def _sim_summary(sim: dict) -> dict:
        """Build a lightweight summary dict from a simulation record."""
        return {
            'id': sim['id'],
            'name': sim.get('name', ''),
            'project_id': sim.get('project_id', ''),
            'status': sim['status'],
            'created_at': sim.get('created_at', ''),
            'max_rounds': sim.get('max_rounds', 0),
            'agent_count': len(sim.get('profiles', [])),
        }

    @classmethod
    def _get_simulation(cls, simulation_id: str) -> dict:
        """Get simulation from memory or disk."""
        with cls._lock:
            if simulation_id not in cls._simulations:
                cls._load_simulation(simulation_id)
            sim = cls._simulations.get(simulation_id)
        if not sim:
            raise FileNotFoundError(
                f"Simulation {simulation_id} not found"
            )
        return sim

    @classmethod
    def _save_simulation(cls, simulation_id: str):
        """Persist simulation metadata to disk."""
        with cls._lock:
            sim = cls._simulations.get(simulation_id)
        if not sim:
            return

        sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
        os.makedirs(sim_dir, exist_ok=True)

        # Save metadata (without large profiles/config which have own files)
        meta = {k: v for k, v in sim.items() if k not in ('profiles', 'config')}
        meta['has_profiles'] = len(sim.get('profiles', [])) > 0
        meta['has_config'] = bool(sim.get('config'))

        path = os.path.join(sim_dir, 'simulation.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    @classmethod
    def _load_simulation(cls, simulation_id: str):
        """Load simulation from disk."""
        sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
        meta_path = os.path.join(sim_dir, 'simulation.json')

        if not os.path.exists(meta_path):
            return

        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        # Load profiles if available
        profiles_path = os.path.join(sim_dir, 'profiles.json')
        if os.path.exists(profiles_path):
            with open(profiles_path, 'r', encoding='utf-8') as f:
                meta['profiles'] = json.load(f)
        else:
            meta['profiles'] = []

        # Load config if available
        config_path = os.path.join(sim_dir, 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                meta['config'] = json.load(f)
        else:
            meta['config'] = {}

        # Note: caller (_get_simulation) already holds _lock
        cls._simulations[simulation_id] = meta

    @classmethod
    def _load_all_from_disk(cls):
        """Load all simulations from disk that aren't already in memory."""
        sims_dir = os.path.join(Config.DATA_DIR, 'simulations')
        if not os.path.exists(sims_dir):
            return

        for name in os.listdir(sims_dir):
            sim_dir = os.path.join(sims_dir, name)
            with cls._lock:
                if name not in cls._simulations and os.path.isdir(sim_dir):
                    cls._load_simulation(name)
