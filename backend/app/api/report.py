"""Report generation API blueprint.

Endpoints:
  POST   /generate                   - start report generation (async)
  POST   /generate/status            - check generation progress
  GET    /list                       - list all reports
  GET    /<id>                       - get complete report
  GET    /<id>/sections              - get all sections
  GET    /<id>/section/<i>           - get specific section
  GET    /<id>/download              - download report as markdown
  GET    /<id>/progress              - real-time generation progress
  GET    /<id>/agent-log             - structured agent event log (JSONL)
  GET    /<id>/console-log           - human-readable console log
  GET    /by-simulation/<sim_id>     - get report by simulation id
  GET    /check/<sim_id>             - check if report exists for simulation
  POST   /chat                       - Q&A with report agent
  POST   /tools/search               - direct graph search
  POST   /tools/statistics           - direct graph statistics
  DELETE /<id>                       - delete report
"""

import json
import threading

from flask import Blueprint, Response, request, jsonify

from app.config import Config
from app.utils.llm_client import LLMClient
from app.utils.report_logger import ReportLogger
from app.utils.validation import validate_id as _validate_id
from app.models.task import TaskManager
from app.services.graph_builder import GraphBuilder
from app.services.report_agent import ReportAgent, _graph_search, _graph_statistics

report_bp = Blueprint("report", __name__)

# Module-level singletons — initialised lazily so the blueprint can be
# registered before the first request.
_llm: LLMClient | None = None
_graph_builder: GraphBuilder | None = None
_report_agent: ReportAgent | None = None
_report_agent_lock = threading.Lock()


def _get_report_agent() -> ReportAgent:
    """Return (or create) the module-level ReportAgent singleton."""
    global _llm, _graph_builder, _report_agent
    if _report_agent is None:
        with _report_agent_lock:
            if _report_agent is None:
                _llm = LLMClient()
                _graph_builder = GraphBuilder(_llm)
                # simulation_engine will be None until another module wires it in.
                _report_agent = ReportAgent(
                    llm_client=_llm,
                    graph_builder=_graph_builder,
                    simulation_engine=None,
                )
    return _report_agent


def set_simulation_engine(engine):
    """Allow external code (e.g. simulation blueprint) to inject the engine."""
    agent = _get_report_agent()
    agent.sim = engine


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@report_bp.route("/generate", methods=["POST"])
def generate_report():
    """Start asynchronous report generation.

    Expects JSON:
    {
        "project_id": "...",
        "graph_id": "..."       (optional — resolved from project if missing)
        "simulation_id": "..."  (optional)
    }
    """
    data = request.get_json() or {}
    project_id = data.get("project_id")
    graph_id = data.get("graph_id")
    simulation_id = data.get("simulation_id", "")

    if not project_id and not graph_id:
        return jsonify({"error": "project_id or graph_id required"}), 400

    # Resolve graph_id from project when missing
    if not graph_id and project_id:
        from app.models.project import Project
        try:
            project = Project.load(project_id)
            graph_id = project.graph_id
        except FileNotFoundError:
            return jsonify({"error": "Project not found"}), 404
        if not graph_id:
            return jsonify({"error": "Project has no graph yet"}), 400

    task = TaskManager.create("generate_report")

    def _run():
        try:
            TaskManager.set_running(task.id)
            agent = _get_report_agent()

            def progress(section: int, total: int):
                pct = int((section + 1) / total * 100) if total else 100
                TaskManager.set_progress(task.id, pct)

            report = agent.generate_report(
                simulation_id=simulation_id,
                graph_id=graph_id,
                project_id=project_id,
                callback=progress,
            )
            TaskManager.set_completed(task.id, {"report_id": report["id"]})
        except Exception as e:
            TaskManager.set_failed(task.id, str(e))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({"task_id": task.id, "message": "Report generation started"})


@report_bp.route("/generate/status", methods=["POST"])
def generate_status():
    """Check report-generation task progress.

    Expects JSON: {"task_id": "..."}
    """
    data = request.get_json() or {}
    task_id = data.get("task_id")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    task = TaskManager.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task.to_dict())


@report_bp.route("/list", methods=["GET"])
def list_reports():
    """List all generated reports (summary only)."""
    agent = _get_report_agent()
    return jsonify(agent.list_reports())


@report_bp.route("/<report_id>", methods=["GET"])
def get_report(report_id: str):
    """Get complete report by id."""
    if not _validate_id(report_id):
        return jsonify({"error": "Invalid report_id"}), 400
    agent = _get_report_agent()
    report = agent.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    return jsonify(report)


@report_bp.route("/<report_id>/sections", methods=["GET"])
def get_sections(report_id: str):
    """Get all sections of a report."""
    if not _validate_id(report_id):
        return jsonify({"error": "Invalid report_id"}), 400
    agent = _get_report_agent()
    report = agent.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    return jsonify(report["sections"])


@report_bp.route("/<report_id>/section/<int:index>", methods=["GET"])
def get_section(report_id: str, index: int):
    """Get a specific section by index."""
    if not _validate_id(report_id):
        return jsonify({"error": "Invalid report_id"}), 400
    agent = _get_report_agent()
    report = agent.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    sections = report["sections"]
    if index < 0 or index >= len(sections):
        return jsonify({"error": f"Section index {index} out of range (0-{len(sections)-1})"}), 404

    return jsonify(sections[index])


@report_bp.route("/chat", methods=["POST"])
def chat_with_report():
    """Post-generation Q&A.

    Expects JSON:
    {
        "report_id": "...",
        "message": "...",
        "graph_id": "..."      (optional)
        "project_id": "..."    (optional)
    }
    """
    data = request.get_json() or {}
    report_id = data.get("report_id")
    message = data.get("message")

    if not report_id or not message:
        return jsonify({"error": "report_id and message required"}), 400

    agent = _get_report_agent()
    answer = agent.chat(
        report_id=report_id,
        message=message,
        graph_id=data.get("graph_id"),
        project_id=data.get("project_id"),
    )
    return jsonify({"answer": answer})


@report_bp.route("/by-simulation/<simulation_id>", methods=["GET"])
def get_report_by_simulation(simulation_id: str):
    """Get report by simulation ID."""
    agent = _get_report_agent()
    report = agent.get_report_by_simulation(simulation_id)
    if report:
        return jsonify(report)
    return jsonify({"error": "No report found for this simulation"}), 404


@report_bp.route("/<report_id>/download", methods=["GET"])
def download_report(report_id: str):
    """Download report as a markdown file."""
    agent = _get_report_agent()
    report = agent.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    # Assemble markdown
    lines = [f"# {report['title']}", ""]
    for section in report["sections"]:
        lines.append(section["content"])
        lines.append("")
    md_content = "\n".join(lines)

    filename = f"report-{report_id}.md"
    return Response(
        md_content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@report_bp.route("/<report_id>/progress", methods=["GET"])
def get_report_progress(report_id: str):
    """Get real-time generation progress for a report.

    Checks tasks for an in-progress generation that produced this report_id,
    or returns completed status if the report already exists.
    """
    agent = _get_report_agent()
    report = agent.get_report(report_id)

    if report:
        section_count = len(report["sections"])
        return jsonify({
            "status": "completed",
            "current_section": section_count,
            "total_sections": section_count,
            "progress_pct": 100,
        })

    # Report not found — might still be generating; check tasks
    return jsonify({
        "status": "not_found",
        "current_section": 0,
        "total_sections": 0,
        "progress_pct": 0,
    }), 404


@report_bp.route("/check/<simulation_id>", methods=["GET"])
def check_report_exists(simulation_id: str):
    """Check if a report exists for a simulation."""
    agent = _get_report_agent()
    report = agent.get_report_by_simulation(simulation_id)
    if report:
        return jsonify({"exists": True, "report_id": report["id"]})
    return jsonify({"exists": False, "report_id": None})


@report_bp.route("/tools/search", methods=["POST"])
def tools_search():
    """Direct graph search tool.

    Expects JSON: {"graph_id": "...", "query": "..."}
    """
    data = request.get_json() or {}
    graph_id = data.get("graph_id")
    query = data.get("query", "")

    if not graph_id:
        return jsonify({"error": "graph_id required"}), 400
    if not query:
        return jsonify({"error": "query required"}), 400

    agent = _get_report_agent()
    try:
        G = agent._load_graph(graph_id=graph_id)
    except FileNotFoundError:
        return jsonify({"error": "Graph not found"}), 404

    result = _graph_search(G, query)
    try:
        return jsonify(json.loads(result))
    except (json.JSONDecodeError, TypeError):
        return jsonify({"result": result})


@report_bp.route("/tools/statistics", methods=["POST"])
def tools_statistics():
    """Direct graph statistics tool.

    Expects JSON: {"graph_id": "..."}
    """
    data = request.get_json() or {}
    graph_id = data.get("graph_id")

    if not graph_id:
        return jsonify({"error": "graph_id required"}), 400

    agent = _get_report_agent()
    try:
        G = agent._load_graph(graph_id=graph_id)
    except FileNotFoundError:
        return jsonify({"error": "Graph not found"}), 404

    result = _graph_statistics(G)
    return jsonify(json.loads(result))


@report_bp.route("/<report_id>/agent-log", methods=["GET"])
def get_agent_log(report_id: str):
    """Stream agent log (JSONL) for a report.

    Query params:
        from_line (int): 0-based line offset (default 0).

    Returns JSON: {"entries": [...], "next_line": N}
    """
    if not _validate_id(report_id):
        return jsonify({"error": "Invalid report_id"}), 400
    from_line = request.args.get("from_line", 0, type=int)
    logger = ReportLogger(report_id, Config.DATA_DIR)
    entries = logger.get_agent_log(from_line)
    return jsonify({
        "entries": entries,
        "next_line": from_line + len(entries),
    })


@report_bp.route("/<report_id>/console-log", methods=["GET"])
def get_console_log(report_id: str):
    """Stream console log (plain text) for a report.

    Query params:
        from_line (int): 0-based line offset (default 0).

    Returns JSON: {"lines": [...], "next_line": N}
    """
    if not _validate_id(report_id):
        return jsonify({"error": "Invalid report_id"}), 400
    from_line = request.args.get("from_line", 0, type=int)
    logger = ReportLogger(report_id, Config.DATA_DIR)
    lines = logger.get_console_log(from_line)
    return jsonify({
        "lines": lines,
        "next_line": from_line + len(lines),
    })


@report_bp.route("/<report_id>", methods=["DELETE"])
def delete_report(report_id: str):
    """Delete a report."""
    if not _validate_id(report_id):
        return jsonify({"error": "Invalid report_id"}), 400
    agent = _get_report_agent()
    if agent.delete_report(report_id):
        return jsonify({"message": "Report deleted"})
    return jsonify({"error": "Report not found"}), 404
