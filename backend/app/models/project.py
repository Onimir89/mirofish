import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from app.config import Config


@dataclass
class Project:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ''
    files: list = field(default_factory=list)
    ontology: dict = field(default_factory=dict)
    graph_id: str = ''
    status: str = 'created'  # created / building / ready / failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    simulation_requirement: str = ''

    def save(self):
        """Save project to JSON file."""
        project_dir = os.path.join(Config.DATA_DIR, 'projects')
        os.makedirs(project_dir, exist_ok=True)
        path = os.path.join(project_dir, f'{self.id}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, project_id: str) -> 'Project':
        """Load project from JSON file."""
        path = os.path.join(Config.DATA_DIR, 'projects', f'{project_id}.json')
        if not os.path.exists(path):
            raise FileNotFoundError(f"Project {project_id} not found")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def list_all(cls) -> list['Project']:
        """List all saved projects."""
        project_dir = os.path.join(Config.DATA_DIR, 'projects')
        if not os.path.exists(project_dir):
            return []
        projects = []
        for fname in os.listdir(project_dir):
            if fname.endswith('.json'):
                try:
                    projects.append(cls.load(fname.replace('.json', '')))
                except Exception:
                    continue
        projects.sort(key=lambda p: p.created_at, reverse=True)
        return projects

    def delete(self):
        """Delete project JSON and its data directory."""
        import shutil
        # Remove project JSON
        path = os.path.join(Config.DATA_DIR, 'projects', f'{self.id}.json')
        if os.path.exists(path):
            os.remove(path)
        # Remove associated graph JSON
        if self.graph_id:
            graph_path = os.path.join(Config.DATA_DIR, 'graphs', f'{self.graph_id}.json')
            if os.path.exists(graph_path):
                os.remove(graph_path)
