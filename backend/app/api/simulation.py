"""Simulation API blueprint."""

import json
import os
import threading

from flask import Blueprint, request, jsonify, send_file

from app.config import Config
from app.services.entity_reader import EntityReader
from app.services.interview_service import InterviewService
from app.services.simulation_manager import SimulationManager
from app.utils.validation import validate_id as _validate_id

# Shared interview service instance (keeps history in-memory)
_interview_service: InterviewService | None = None
_interview_service_lock = threading.Lock()


def _get_interview_service() -> InterviewService:
    global _interview_service
    if _interview_service is None:
        with _interview_service_lock:
            if _interview_service is None:
                from app.utils.llm_client import LLMClient
                _interview_service = InterviewService(LLMClient())
    return _interview_service


def _require_simulation_id() -> tuple[dict, str] | tuple[None, None]:
    """Parse JSON body and extract simulation_id, or return (None, None).

    Returns (data, simulation_id) on success, or aborts with a 400 response.
    """
    data = request.get_json()
    if not data or 'simulation_id' not in data:
        return None, None
    return data, data['simulation_id']


def _paginated_params(default_limit: int = 50, max_limit: int = 200) -> tuple[int, int]:
    """Extract offset/limit from query params with bounds."""
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', default_limit, type=int)
    return offset, min(limit, max_limit)


simulation_bp = Blueprint('simulation', __name__)


@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """Create a new simulation.

    Expects JSON:
    {
        "project_id": "...",
        "name": "optional name",
        "max_rounds": 10,
        "max_agents": null
    }
    """
    data = request.get_json()
    if not data or 'project_id' not in data:
        return jsonify({'error': 'project_id is required'}), 400

    try:
        sim = SimulationManager.create_simulation(
            project_id=data['project_id'],
            name=data.get('name', ''),
            max_rounds=data.get('max_rounds'),
            max_agents=data.get('max_agents'),
        )
        return jsonify(sim)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """Prepare simulation (generate profiles + config, async)."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        sim = SimulationManager.prepare_simulation(sim_id)
        return jsonify({
            'simulation_id': sim['id'],
            'status': sim['status'],
            'message': 'Preparation started',
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@simulation_bp.route('/prepare/status', methods=['POST'])
def prepare_status():
    """Check preparation progress."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        status = SimulationManager.get_prep_status(sim_id)
        return jsonify(status)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/history', methods=['GET'])
def list_simulation_history():
    """List simulations with run state info (recent actions, round progress).

    Query params:
        limit: max results (default 20)
    """
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)
    history = SimulationManager.list_simulations_with_history(limit)
    return jsonify({'simulations': history, 'count': len(history)})


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Get simulation metadata."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        sim = SimulationManager.get_simulation(simulation_id)
        # Return without large nested data
        return jsonify({
            'id': sim['id'],
            'name': sim.get('name', ''),
            'project_id': sim.get('project_id', ''),
            'graph_id': sim.get('graph_id', ''),
            'status': sim['status'],
            'max_rounds': sim.get('max_rounds', 0),
            'max_agents': sim.get('max_agents'),
            'created_at': sim.get('created_at', ''),
            'agent_count': len(sim.get('profiles', [])),
            'has_config': bool(sim.get('config')),
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """List all simulations."""
    sims = SimulationManager.list_simulations()
    return jsonify(sims)


@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """Start simulation execution."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        sim = SimulationManager.start_simulation(sim_id)
        return jsonify({
            'simulation_id': sim['id'],
            'status': sim['status'],
            'message': 'Simulation started',
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """Stop a running simulation."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        sim = SimulationManager.stop_simulation(sim_id)
        return jsonify({
            'simulation_id': sim['id'],
            'status': sim['status'],
            'message': 'Simulation stopped',
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def run_status(simulation_id: str):
    """Get simulation run status summary."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        status = SimulationManager.get_status(simulation_id)
        return jsonify(status)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def run_status_detail(simulation_id: str):
    """Get detailed run status with recent actions."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        detail = SimulationManager.get_detail_status(simulation_id)
        return jsonify(detail)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_actions(simulation_id: str):
    """Get paginated action history."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    offset, limit = _paginated_params()

    try:
        actions = SimulationManager.get_actions(simulation_id, offset, limit)
        return jsonify({
            'actions': actions,
            'offset': offset,
            'limit': limit,
            'count': len(actions),
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_timeline(simulation_id: str):
    """Get timeline grouped by rounds."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        timeline = SimulationManager.get_timeline(simulation_id)
        return jsonify({'rounds': timeline})
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """Get per-agent statistics."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        stats = SimulationManager.get_agent_stats(simulation_id)
        return jsonify({'agents': stats})
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_profiles(simulation_id: str):
    """Get agent profiles."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        profiles = SimulationManager.get_profiles(simulation_id)
        return jsonify({'profiles': profiles})
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_config(simulation_id: str):
    """Get simulation config."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    try:
        config = SimulationManager.get_config(simulation_id)
        return jsonify({'config': config})
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


# ---------------------------------------------------------------------------
# Realtime & download endpoints
# ---------------------------------------------------------------------------

def _get_prep_status_safe(simulation_id: str) -> tuple[str, int]:
    """Get prep status/progress, returning ('unknown', 0) on failure."""
    try:
        status = SimulationManager.get_prep_status(simulation_id)
        return status.get('status', 'unknown'), status.get('progress', 0)
    except FileNotFoundError:
        return 'unknown', 0


def _load_realtime_json(path: str, default):
    """Load a JSON file, returning default on missing/corrupt data."""
    if not os.path.exists(path):
        return None  # signals file not yet created
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_profiles_realtime(simulation_id: str):
    """Get profiles as they're being generated (partial results)."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400

    sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
    profiles = _load_realtime_json(os.path.join(sim_dir, 'profiles.json'), [])

    if profiles is None:
        # File not yet created — return empty with preparing status
        try:
            status = SimulationManager.get_prep_status(simulation_id)
        except FileNotFoundError as e:
            return jsonify({'error': str(e)}), 404
        return jsonify({
            'profiles': [],
            'count': 0,
            'status': status.get('status', 'unknown'),
            'progress': status.get('progress', 0),
        })

    platform = request.args.get('platform')
    if platform:
        profiles = [
            p for p in profiles
            if p.get('platform', '').lower() == platform.lower()
        ]

    prep_status, prep_progress = _get_prep_status_safe(simulation_id)
    return jsonify({
        'profiles': profiles,
        'count': len(profiles),
        'status': prep_status,
        'progress': prep_progress,
    })


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_config_realtime(simulation_id: str):
    """Get config as it's being generated (partial results)."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400

    sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
    config = _load_realtime_json(os.path.join(sim_dir, 'config.json'), {})

    if config is None:
        try:
            status = SimulationManager.get_prep_status(simulation_id)
        except FileNotFoundError as e:
            return jsonify({'error': str(e)}), 404
        return jsonify({
            'config': {},
            'status': status.get('status', 'unknown'),
            'progress': status.get('progress', 0),
        })

    prep_status, prep_progress = _get_prep_status_safe(simulation_id)
    return jsonify({
        'config': config,
        'status': prep_status,
        'progress': prep_progress,
    })


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_config(simulation_id: str):
    """Download simulation config as JSON file attachment."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    sim_dir = os.path.join(Config.DATA_DIR, 'simulations', simulation_id)
    config_path = os.path.join(sim_dir, 'config.json')

    if not os.path.exists(config_path):
        try:
            SimulationManager.get_simulation(simulation_id)
            return jsonify({'error': 'Config not yet generated'}), 404
        except FileNotFoundError as e:
            return jsonify({'error': str(e)}), 404

    return send_file(
        config_path,
        mimetype='application/json',
        as_attachment=True,
        download_name=f'simulation_{simulation_id}_config.json',
    )


@simulation_bp.route('/env-status', methods=['POST'])
def env_status():
    """Get simulation environment status."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        status = SimulationManager.get_env_status(sim_id)
        return jsonify(status)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/close-env', methods=['POST'])
def close_env():
    """Close simulation environment and free resources."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        result = SimulationManager.close_env(sim_id)
        return jsonify(result)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """Regenerate agent profiles for a simulation."""
    data, simulation_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    try:
        sim = SimulationManager.get_simulation(simulation_id)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404

    if sim['status'] not in ('created', 'ready', 'failed', 'stopped'):
        return jsonify({
            'error': f"Cannot regenerate profiles in status '{sim['status']}'"
        }), 400

    def _generate():
        try:
            from app.utils.llm_client import LLMClient
            from app.models.project import Project
            from app.services.profile_generator import ProfileGenerator

            llm = LLMClient()
            project = Project.load(sim['project_id'])
            profile_gen = ProfileGenerator(llm)

            profiles = profile_gen.generate_profiles_batch(
                graph_id=sim['graph_id'],
                requirement=project.simulation_requirement,
                entity_type=data.get('entity_type'),
                max_agents=data.get('max_agents') or sim.get('max_agents'),
            )
            profile_gen.save_profiles(simulation_id, profiles)

            # Update in-memory state
            with SimulationManager._lock:
                s = SimulationManager._simulations.get(simulation_id)
                if s:
                    s['profiles'] = profiles

        except Exception as e:
            with SimulationManager._lock:
                s = SimulationManager._simulations.get(simulation_id)
                if s:
                    s['prep_error'] = f"Profile generation failed: {e}"

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()

    return jsonify({
        'simulation_id': simulation_id,
        'message': 'Profile generation started in background',
    })


# ---------------------------------------------------------------------------
# Entity endpoints
# ---------------------------------------------------------------------------

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_entities(graph_id: str):
    """Get all entities from a knowledge graph with edges and neighbors."""
    try:
        reader = EntityReader()
        entities = reader.get_entities(graph_id)
        return jsonify({'entities': entities, 'count': len(entities)})
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity(graph_id: str, entity_uuid: str):
    """Get a single entity by UUID with full details."""
    try:
        reader = EntityReader()
        entity = reader.get_entity(graph_id, entity_uuid)
        if entity is None:
            return jsonify({'error': f'Entity {entity_uuid} not found'}), 404
        return jsonify(entity)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Get all entities of a specific type from the graph."""
    try:
        reader = EntityReader()
        entities = reader.get_entities(graph_id, entity_type=entity_type)
        return jsonify({
            'entities': entities,
            'count': len(entities),
            'entity_type': entity_type,
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500



def _validate_platform() -> tuple[str | None, dict | None]:
    """Validate optional platform query param. Returns (platform, error_response)."""
    platform = request.args.get('platform')
    if platform and platform not in ('twitter', 'reddit'):
        return None, jsonify({'error': 'platform must be twitter or reddit'})
    return platform, None


@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_posts(simulation_id: str):
    """Get posts from a simulation."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    platform, err = _validate_platform()
    if err:
        return err, 400
    offset, limit = _paginated_params()

    try:
        SimulationManager.get_simulation(simulation_id)
        posts = SimulationManager.get_posts(
            simulation_id, platform=platform, offset=offset, limit=limit,
        )
        return jsonify({
            'posts': posts,
            'offset': offset,
            'limit': limit,
            'count': len(posts),
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@simulation_bp.route('/<simulation_id>/comments', methods=['GET'])
def get_comments(simulation_id: str):
    """Get comments from a simulation."""
    if not _validate_id(simulation_id):
        return jsonify({'error': 'Invalid simulation_id'}), 400
    platform, err = _validate_platform()
    if err:
        return err, 400
    offset, limit = _paginated_params()

    try:
        SimulationManager.get_simulation(simulation_id)
        comments = SimulationManager.get_comments(
            simulation_id, platform=platform, offset=offset, limit=limit,
        )
        return jsonify({
            'comments': comments,
            'offset': offset,
            'limit': limit,
            'count': len(comments),
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


# ---------------------------------------------------------------------------
# Interview endpoints
# ---------------------------------------------------------------------------

def _get_agent_context(simulation_id: str, agent_id: str) -> list[dict]:
    """Gather recent posts/actions by a specific agent for interview context."""
    with SimulationManager._lock:
        engine = SimulationManager._engines.get(simulation_id)
    if not engine:
        return []

    context = []
    for action in engine.state.actions:
        a = action if isinstance(action, dict) else action.to_dict()
        if a.get('agent_id') == agent_id and a.get('content'):
            context.append(a)
    # Return most recent 10
    return context[-10:]


@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """Interview a single agent.

    Expects JSON:
    {
        "simulation_id": "...",
        "agent_id": "...",
        "question": "..."
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body is required'}), 400
    for field in ('simulation_id', 'agent_id', 'question'):
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    simulation_id = data['simulation_id']
    agent_id = data['agent_id']
    question = data['question']

    try:
        sim = SimulationManager.get_simulation(simulation_id)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404

    profiles = sim.get('profiles', [])
    profile = next((p for p in profiles if p.get('agent_id') == agent_id), None)
    if not profile:
        return jsonify({'error': f'Agent {agent_id} not found'}), 404

    context = _get_agent_context(simulation_id, agent_id)
    service = _get_interview_service()
    result = service.interview_agent(profile, question, context)
    service.record_interviews(simulation_id, [result])

    return jsonify(result)


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_batch():
    """Interview multiple agents.

    Expects JSON:
    {
        "simulation_id": "...",
        "interviews": [
            {"agent_id": "...", "question": "..."},
            ...
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body is required'}), 400
    if 'simulation_id' not in data:
        return jsonify({'error': 'simulation_id is required'}), 400
    if 'interviews' not in data or not isinstance(data['interviews'], list):
        return jsonify({'error': 'interviews array is required'}), 400

    simulation_id = data['simulation_id']

    try:
        sim = SimulationManager.get_simulation(simulation_id)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404

    profiles = sim.get('profiles', [])
    profile_map = {p.get('agent_id'): p for p in profiles}

    service = _get_interview_service()
    results = []
    errors = []

    for item in data['interviews']:
        agent_id = item.get('agent_id', '')
        question = item.get('question', '')
        if not agent_id or not question:
            errors.append({'agent_id': agent_id, 'error': 'agent_id and question required'})
            continue

        profile = profile_map.get(agent_id)
        if not profile:
            errors.append({'agent_id': agent_id, 'error': f'Agent {agent_id} not found'})
            continue

        context = _get_agent_context(simulation_id, agent_id)
        result = service.interview_agent(profile, question, context)
        results.append(result)

    service.record_interviews(simulation_id, results)

    response = {'interviews': results, 'count': len(results)}
    if errors:
        response['errors'] = errors
    return jsonify(response)


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all():
    """Interview all agents with the same question.

    Expects JSON:
    {
        "simulation_id": "...",
        "question": "..."
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body is required'}), 400
    for field in ('simulation_id', 'question'):
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    simulation_id = data['simulation_id']
    question = data['question']

    try:
        sim = SimulationManager.get_simulation(simulation_id)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404

    profiles = sim.get('profiles', [])
    if not profiles:
        return jsonify({'error': 'No agents in this simulation'}), 400

    # Build context map for all agents
    context_map: dict[str, list[dict]] = {}
    for profile in profiles:
        aid = profile.get('agent_id', '')
        context_map[aid] = _get_agent_context(simulation_id, aid)

    service = _get_interview_service()
    results = service.interview_all(profiles, question, context_map)
    service.record_interviews(simulation_id, results)

    return jsonify({'interviews': results, 'count': len(results)})


@simulation_bp.route('/interview/history', methods=['POST'])
def interview_history():
    """Get interview history for a simulation."""
    data, sim_id = _require_simulation_id()
    if not data:
        return jsonify({'error': 'simulation_id is required'}), 400

    service = _get_interview_service()
    history = service.get_history(sim_id)
    return jsonify({'interviews': history, 'count': len(history)})
