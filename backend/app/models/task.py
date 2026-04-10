import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class AsyncTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ''
    status: str = 'pending'  # pending / running / completed / failed
    progress: int = 0
    result: dict = field(default_factory=dict)
    error: str = ''
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class TaskManager:
    """In-memory async task tracker."""

    _tasks: dict[str, AsyncTask] = {}

    @classmethod
    def create(cls, task_type: str) -> AsyncTask:
        task = AsyncTask(type=task_type)
        cls._tasks[task.id] = task
        return task

    @classmethod
    def get(cls, task_id: str) -> AsyncTask | None:
        return cls._tasks.get(task_id)

    @classmethod
    def update(cls, task_id: str, **kwargs):
        task = cls._tasks.get(task_id)
        if not task:
            return
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = datetime.now().isoformat()

    @classmethod
    def set_running(cls, task_id: str):
        cls.update(task_id, status='running')

    @classmethod
    def set_completed(cls, task_id: str, result: dict = None):
        cls.update(task_id, status='completed', progress=100, result=result or {})

    @classmethod
    def set_failed(cls, task_id: str, error: str):
        cls.update(task_id, status='failed', error=error)

    @classmethod
    def set_progress(cls, task_id: str, progress: int):
        cls.update(task_id, progress=min(progress, 100))

    @classmethod
    def list_all(cls) -> list[AsyncTask]:
        """Return all tracked tasks, newest first."""
        tasks = list(cls._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks
