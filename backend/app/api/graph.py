import os
import threading
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from app.config import Config
from app.utils.llm_client import LLMClient
from app.utils.validation import validate_id as _validate_id
from app.models.project import Project
from app.models.task import TaskManager
from app.services.text_processor import TextProcessor
from app.services.ontology_generator import OntologyGenerator
from app.services.graph_builder import GraphBuilder
from app.services.entity_reader import EntityReader

graph_bp = Blueprint('graph', __name__)


def _allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """Generate ontology from uploaded files + simulation requirement.

    Expects multipart form with:
    - files: uploaded document files
    - requirement: simulation requirement text
    - name: project name (optional)
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    requirement = request.form.get('requirement', '')
    project_name = request.form.get('name', 'Untitled Project')

    # Save uploaded files in per-project subdirectory to avoid collisions
    import uuid as _uuid
    project_id_tmp = str(_uuid.uuid4())[:12]
    upload_dir = os.path.join(Config.DATA_DIR, 'uploads', project_id_tmp)
    os.makedirs(upload_dir, exist_ok=True)

    file_paths = []
    saved_filenames = []
    for f in files:
        if f and f.filename and _allowed_file(f.filename):
            filename = secure_filename(f.filename)
            filepath = os.path.join(upload_dir, filename)
            f.save(filepath)
            file_paths.append((filepath, filename))
            saved_filenames.append(filename)

    if not file_paths:
        return jsonify({'error': 'No valid files uploaded'}), 400

    # Extract text from files
    processor = TextProcessor()
    parsed = processor.extract_from_files(file_paths)
    texts = [p['content'] for p in parsed if p['content']]

    if not texts:
        return jsonify({'error': 'Could not extract text from files'}), 400

    # Generate ontology
    llm = LLMClient()
    generator = OntologyGenerator(llm)
    ontology = generator.generate(texts, requirement)

    # Create project
    project = Project(
        name=project_name,
        files=saved_filenames,
        ontology=ontology,
        simulation_requirement=requirement,
    )
    project.save()

    return jsonify({
        'project_id': project.id,
        'ontology': ontology,
        'files': saved_filenames,
    })


@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """Build knowledge graph asynchronously.

    Expects JSON:
    {
        "project_id": "...",
        "ontology": {...}  (optional, uses project ontology if not provided)
    }
    """
    data = request.get_json()
    if not data or 'project_id' not in data:
        return jsonify({'error': 'project_id required'}), 400

    project_id = data['project_id']

    try:
        project = Project.load(project_id)
    except FileNotFoundError:
        return jsonify({'error': 'Project not found'}), 404

    ontology = data.get('ontology', project.ontology)
    if not ontology:
        return jsonify({'error': 'No ontology available'}), 400

    # Create async task
    task = TaskManager.create('build_graph')

    # Run graph building in background thread
    def _build():
        try:
            TaskManager.set_running(task.id)
            project.status = 'building'
            project.save()

            # Read file contents (check per-project subdirs first, then flat)
            processor = TextProcessor()
            base_upload_dir = os.path.join(Config.DATA_DIR, 'uploads')
            file_paths = []
            for fn in project.files:
                # Try per-project subdirectories first
                found = False
                if os.path.isdir(base_upload_dir):
                    for subdir in os.listdir(base_upload_dir):
                        candidate = os.path.join(base_upload_dir, subdir, fn)
                        if os.path.isfile(candidate):
                            file_paths.append((candidate, fn))
                            found = True
                            break
                if not found:
                    file_paths.append((os.path.join(base_upload_dir, fn), fn))
            parsed = processor.extract_from_files(file_paths)
            combined_text = '\n\n'.join(p['content'] for p in parsed if p['content'])

            # Clean up uploaded files after extraction
            for fpath, _ in file_paths:
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                        # Remove parent dir if empty
                        parent = os.path.dirname(fpath)
                        if parent != base_upload_dir and os.path.isdir(parent) and not os.listdir(parent):
                            os.rmdir(parent)
                except OSError:
                    pass

            # Chunk text
            chunks = processor.split_text(
                combined_text,
                chunk_size=Config.DEFAULT_CHUNK_SIZE,
                overlap=Config.DEFAULT_CHUNK_OVERLAP,
            )

            if not chunks:
                raise ValueError("No text chunks generated")

            # Build graph
            llm = LLMClient()
            builder = GraphBuilder(llm)

            def progress_callback(progress: int):
                TaskManager.set_progress(task.id, progress)

            graph_id, graph_info = builder.build_graph(
                project_id, chunks, ontology, callback=progress_callback
            )

            # Update project
            project.graph_id = graph_id
            project.ontology = ontology
            project.status = 'ready'
            project.save()

            TaskManager.set_completed(task.id, {
                'graph_id': graph_id,
                'graph_info': graph_info,
            })

        except Exception as e:
            project.status = 'failed'
            project.save()
            TaskManager.set_failed(task.id, str(e))

    thread = threading.Thread(target=_build, daemon=True)
    thread.start()

    return jsonify({
        'task_id': task.id,
        'message': 'Graph building started',
    })


@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """Get async task status."""
    if not _validate_id(task_id):
        return jsonify({'error': 'Invalid task_id'}), 400
    task = TaskManager.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task.to_dict())


@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """Get graph nodes/edges for D3 visualization."""
    if not _validate_id(graph_id):
        return jsonify({'error': 'Invalid graph_id'}), 400
    try:
        reader = EntityReader()
        data = reader.get_graph_data(graph_id)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Graph not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """Get project info."""
    if not _validate_id(project_id):
        return jsonify({'error': 'Invalid project_id'}), 400
    try:
        project = Project.load(project_id)
        return jsonify({
            'id': project.id,
            'name': project.name,
            'files': project.files,
            'ontology': project.ontology,
            'graph_id': project.graph_id,
            'status': project.status,
            'created_at': project.created_at,
            'simulation_requirement': project.simulation_requirement,
        })
    except FileNotFoundError:
        return jsonify({'error': 'Project not found'}), 404


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """List all projects."""
    projects = Project.list_all()
    return jsonify([
        {
            'id': p.id,
            'name': p.name,
            'status': p.status,
            'created_at': p.created_at,
            'file_count': len(p.files),
            'graph_id': p.graph_id,
        }
        for p in projects
    ])


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """Delete a project and its associated data."""
    if not _validate_id(project_id):
        return jsonify({'error': 'Invalid project_id'}), 400
    try:
        project = Project.load(project_id)
    except FileNotFoundError:
        return jsonify({'error': 'Project not found'}), 404

    project.delete()
    return jsonify({'message': f'Project {project_id} deleted'})


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """Reset a project to re-build graph."""
    if not _validate_id(project_id):
        return jsonify({'error': 'Invalid project_id'}), 400
    try:
        project = Project.load(project_id)
    except FileNotFoundError:
        return jsonify({'error': 'Project not found'}), 404

    # Remove existing graph JSON if present
    if project.graph_id:
        graph_path = os.path.join(Config.DATA_DIR, 'graphs', f'{project.graph_id}.json')
        if os.path.exists(graph_path):
            os.remove(graph_path)

    project.graph_id = ''
    project.status = 'created'
    project.save()

    return jsonify({'message': f'Project {project_id} reset to created'})


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """List all tasks."""
    tasks = TaskManager.list_all()
    return jsonify([
        {
            'id': t.id,
            'type': t.type,
            'status': t.status,
            'progress': t.progress,
            'created_at': t.created_at,
        }
        for t in tasks
    ])


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """Delete a graph JSON file."""
    if not _validate_id(graph_id):
        return jsonify({'error': 'Invalid graph_id'}), 400
    graph_path = os.path.join(Config.DATA_DIR, 'graphs', f'{graph_id}.json')
    if not os.path.exists(graph_path):
        return jsonify({'error': 'Graph not found'}), 404
    os.remove(graph_path)
    return jsonify({'message': f'Graph {graph_id} deleted'})
