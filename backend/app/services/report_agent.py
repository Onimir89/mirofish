"""ReACT-based report generation agent.

Flow:
1. Planning phase - get graph/simulation stats, create report outline
2. Generation phase - ReACT loop per section with tool calls
3. Chat phase - post-generation Q&A
"""

import re
import uuid
import json
import threading
from datetime import datetime

import networkx as nx

from app.utils.llm_client import LLMClient
from app.utils.report_logger import ReportLogger
from app.config import Config


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = """\
You are a senior research analyst. Given detailed statistics about a knowledge \
graph and simulation, create an outline for a rigorous analytical report.

Return JSON with this exact structure:
{
  "title": "Report title",
  "sections": [
    {
      "title": "Section title",
      "focus": "What this section should cover",
      "key_questions": ["Question 1 to answer", "Question 2 to answer"],
      "suggested_tools": ["graph_search", "simulation_summary"]
    }
  ]
}

Requirements:
- Create between 3 and 5 sections. Each section must have a clear analytical \
focus with specific questions to investigate.
- Section titles should reflect analytical depth (e.g. "Power-Law Distribution \
in Entity Connectivity" not "Graph Overview").
- Each section must specify 2-3 key questions that drive the analysis.
- Suggest which tools to use per section.
- Do NOT include introduction/conclusion boilerplate — every section must \
deliver substance and insight.
- Sections should progress logically: structure → patterns → dynamics → implications."""

REACT_SYSTEM_PROMPT = """\
You are a senior research analyst generating one section of an analytical report.
You MUST gather substantial evidence before writing. Make at least 3 tool calls.

Available tools — use exactly this XML format, one per line:

<tool_call>graph_search|query text</tool_call>
<tool_call>graph_statistics|</tool_call>
<tool_call>simulation_summary|</tool_call>
<tool_call>agent_interview|agent_id|question</tool_call>

Strategy:
1. Start with broad tools (graph_statistics, simulation_summary) for context.
2. Use graph_search with specific queries to find evidence for claims.
3. Use agent_interview to get qualitative perspectives when relevant.

After gathering enough information, write your final section as:

Final Answer:
[your section content]

Section content requirements:
- Use ## for the section title, ### for subsections
- Minimum 500 words of substantive analysis
- Cite specific evidence from tool results (entity names, counts, relationships)
- Include both quantitative findings and analytical interpretation
- Use markdown: headers, bullet lists, bold for key terms, > for quotes
- Structure as: context → findings → analysis → implications
- Do NOT just describe data — explain what it means and why it matters"""

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are a senior research analyst writing the section "{title}" of an analytical report.

Section focus: {focus}
Key questions to investigate:
{key_questions}

You MUST gather substantial evidence before writing. Make at least 3 tool calls.
Suggested tools for this section: {suggested_tools}

Available tools — use exactly this XML format, one per line:

<tool_call>graph_search|query text</tool_call>
<tool_call>graph_statistics|</tool_call>
<tool_call>simulation_summary|</tool_call>
<tool_call>agent_interview|agent_id|question</tool_call>

Strategy:
1. Start with broad tools (graph_statistics, simulation_summary) for context.
2. Use graph_search with targeted queries relevant to "{focus}".
3. Use agent_interview to get qualitative perspectives when relevant.
4. Cross-reference findings across multiple tool results.

After gathering enough information, write your final section as:

Final Answer:
[your section content]

Section content requirements:
- Use ## for the section title, ### for subsections
- Minimum 500 words of substantive analysis
- Cite specific evidence from tool results (entity names, counts, relationships)
- Include both quantitative findings and analytical interpretation
- Use markdown: headers, bullet lists, bold for key terms, > for quotes
- Structure as: context → findings → analysis → implications
- Do NOT just describe data — explain what it means and why it matters
- Answer the key questions listed above with evidence"""

CHAT_SYSTEM_PROMPT = """\
You are a research analyst who has generated a report. Answer follow-up \
questions using the report context and available tools.

Report title: {title}

Report content:
{content}

You can use tools to look up additional information:
<tool_call>graph_search|query text</tool_call>
<tool_call>graph_statistics|</tool_call>
<tool_call>simulation_summary|</tool_call>
<tool_call>agent_interview|agent_id|question</tool_call>

If you use a tool, wait for the Observation before answering.
When ready, write:
Final Answer:
[your answer]"""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _graph_search(G: nx.DiGraph, query: str) -> str:
    """Search entities and edges in the graph by keyword."""
    query_lower = query.lower()
    results = {"entities": [], "edges": []}

    for node_id, data in G.nodes(data=True):
        name = data.get("name", "")
        desc = data.get("description", "")
        if query_lower in name.lower() or query_lower in desc.lower():
            results["entities"].append({
                "id": node_id,
                "name": name,
                "type": data.get("type", ""),
                "description": desc[:200],
            })
            if len(results["entities"]) >= Config.SEARCH_RESULT_LIMIT:
                break

    for u, v, data in G.edges(data=True):
        fact = data.get("fact", "")
        rel = data.get("relation", "")
        if query_lower in fact.lower() or query_lower in rel.lower():
            src = G.nodes[u].get("name", u)
            tgt = G.nodes[v].get("name", v)
            results["edges"].append({
                "source": src,
                "relation": rel,
                "target": tgt,
                "fact": fact[:200],
            })
            if len(results["edges"]) >= Config.SEARCH_RESULT_LIMIT:
                break

    if not results["entities"] and not results["edges"]:
        return f"No results found for '{query}'."
    return json.dumps(results, ensure_ascii=False, indent=2)


def _graph_statistics(G: nx.DiGraph) -> str:
    """Return graph statistics."""
    type_counts: dict[str, int] = {}
    for _, data in G.nodes(data=True):
        t = data.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    edge_types: dict[str, int] = {}
    for _, _, data in G.edges(data=True):
        r = data.get("relation", "UNKNOWN")
        edge_types[r] = edge_types.get(r, 0) + 1

    stats = {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "entity_types": type_counts,
        "relationship_types": edge_types,
        "density": round(nx.density(G), 4),
    }

    # Top entities by connections
    if G.number_of_nodes() > 0:
        degree = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:10]
        stats["top_connected"] = [
            {"name": G.nodes[n].get("name", n), "connections": d}
            for n, d in degree
        ]

    return json.dumps(stats, ensure_ascii=False, indent=2)


def _simulation_summary(sim_engine, simulation_id: str) -> str:
    """Get simulation actions summary. Works even if engine is None."""
    if sim_engine is None:
        return json.dumps({"status": "no_simulation", "message": "No simulation data available."})

    # Try common API patterns the simulation engine might expose
    try:
        if hasattr(sim_engine, "get_summary"):
            return json.dumps(sim_engine.get_summary(simulation_id), ensure_ascii=False, indent=2)
        if hasattr(sim_engine, "get_simulation"):
            sim = sim_engine.get_simulation(simulation_id)
            if sim and isinstance(sim, dict):
                return json.dumps(sim, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

    return json.dumps({"status": "no_data", "message": "Simulation engine has no summary method."})


def _agent_interview(llm: LLMClient, sim_engine, agent_id: str, question: str) -> str:
    """Ask a simulation agent a question via LLM."""
    # Get agent profile from simulation engine if available
    agent_profile = ""
    if sim_engine is not None:
        try:
            if hasattr(sim_engine, "get_agent"):
                agent = sim_engine.get_agent(agent_id)
                if agent:
                    agent_profile = json.dumps(agent, ensure_ascii=False, indent=2) if isinstance(agent, dict) else str(agent)
            elif hasattr(sim_engine, "agents") and isinstance(sim_engine.agents, dict):
                agent = sim_engine.agents.get(agent_id)
                if agent:
                    agent_profile = str(agent)
        except Exception:
            pass

    if not agent_profile:
        return f"Agent '{agent_id}' not found in the simulation."

    messages = [
        {
            "role": "system",
            "content": (
                f"You are agent {agent_id} in a social simulation. "
                f"Your profile:\n{agent_profile}\n\n"
                "Answer the question in-character, based on your profile and actions."
            ),
        },
        {"role": "user", "content": question},
    ]
    return llm.chat(messages)


# ---------------------------------------------------------------------------
# ReportAgent
# ---------------------------------------------------------------------------

class ReportAgent:
    """ReACT-based agent that generates analytical reports from graph + simulation data."""

    def __init__(self, llm_client: LLMClient = None, graph_builder=None, simulation_engine=None):
        self.llm = llm_client or LLMClient()
        self.graph_builder = graph_builder
        self.sim = simulation_engine
        self.reports: dict[str, dict] = {}  # report_id -> report data
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(self, simulation_id: str, graph_id: str = None,
                        project_id: str = None, callback=None) -> dict:
        """Generate a full report.

        Args:
            simulation_id: Simulation identifier (may be empty).
            graph_id: Graph to analyse. Falls back to project's graph.
            project_id: Project id — used to resolve graph_id if not given.
            callback: Progress fn(section=int, total=int).

        Returns:
            Report dict with id, title, sections, created_at, metadata.
        """
        # Create a preliminary report id so the logger can write to its dir
        report_id = str(uuid.uuid4())[:8]
        logger = ReportLogger(report_id, Config.DATA_DIR)
        logger.log_event("report_start", {
            "report_id": report_id,
            "simulation_id": simulation_id,
            "graph_id": graph_id,
            "project_id": project_id,
        })
        logger.log_console(f"Report generation started (id={report_id})")

        # Resolve graph
        G = self._load_graph(graph_id, project_id)

        # 1. Plan
        logger.log_event("planning_start")
        logger.log_console("Planning report outline...")
        outline = self._plan_report(G, simulation_id)
        logger.log_event("planning_complete", {"outline": outline})
        logger.log_console(f"Outline ready: {len(outline.get('sections', []))} sections")

        # 2. Generate sections
        sections = []
        total = len(outline.get("sections", []))
        for i, section_plan in enumerate(outline["sections"]):
            logger.log_event("section_start", {
                "index": i,
                "title": section_plan["title"],
                "focus": section_plan["focus"],
            })
            logger.log_console(f"Generating section {i+1}/{total}: {section_plan['title']}")

            content = self._generate_section(G, simulation_id, section_plan, i,
                                             logger=logger)
            sections.append({
                "index": i,
                "title": section_plan["title"],
                "focus": section_plan["focus"],
                "content": content,
            })

            logger.log_event("section_complete", {"index": i, "title": section_plan["title"]})
            logger.log_console(f"Section {i+1}/{total} complete")

            if callback:
                callback(section=i, total=total)

        # 3. Assemble
        report = self._assemble_report(outline, sections, report_id=report_id)
        report["simulation_id"] = simulation_id or ""
        report["graph_id"] = graph_id or ""
        report["project_id"] = project_id or ""
        with self._lock:
            self.reports[report["id"]] = report

        logger.log_event("report_complete", {"report_id": report["id"], "title": report["title"]})
        logger.log_console("Report generation complete")

        return report

    def chat(self, report_id: str, message: str, graph_id: str = None,
             project_id: str = None) -> str:
        """Post-generation Q&A with report context + tools."""
        with self._lock:
            report = self.reports.get(report_id)
        if not report:
            return "Report not found."

        G = self._load_graph(graph_id or report.get("graph_id"),
                             project_id or report.get("project_id"))

        full_content = "\n\n".join(s["content"] for s in report["sections"])
        system = CHAT_SYSTEM_PROMPT.format(
            title=report["title"],
            content=full_content[:Config.CONTEXT_MAX_CHARS],
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ]

        return self._react_loop(messages, G, report.get("simulation_id", ""),
                                max_tools=Config.REPORT_AGENT_MAX_TOOL_CALLS,
                                min_tools=0)

    def get_report(self, report_id: str) -> dict | None:
        with self._lock:
            return self.reports.get(report_id)

    def list_reports(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "section_count": len(r["sections"]),
                    "created_at": r["created_at"],
                }
                for r in self.reports.values()
            ]

    def delete_report(self, report_id: str) -> bool:
        with self._lock:
            return self.reports.pop(report_id, None) is not None

    def get_report_by_simulation(self, simulation_id: str) -> dict | None:
        """Find a report by simulation ID (thread-safe)."""
        with self._lock:
            for report in self.reports.values():
                sim_id = report.get("simulation_id", "") or report.get("metadata", {}).get("simulation_id", "")
                if sim_id == simulation_id:
                    return report
        return None

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _plan_report(self, G: nx.DiGraph, simulation_id: str) -> dict:
        """Ask LLM to plan a report outline based on graph + simulation stats."""
        stats = _graph_statistics(G)
        sim_info = _simulation_summary(self.sim, simulation_id)

        # Detailed graph analysis for the planner
        detailed_graph_info = self._compute_detailed_graph_stats(G)

        # Sample entities (top connected first for relevance)
        sample_entities = []
        if G.number_of_nodes() > 0:
            sorted_nodes = sorted(G.degree(), key=lambda x: x[1], reverse=True)
            for node_id, degree in sorted_nodes[:Config.SAMPLE_ENTITIES_LIMIT]:
                data = G.nodes[node_id]
                sample_entities.append({
                    "name": data.get("name", ""),
                    "type": data.get("type", ""),
                    "connections": degree,
                    "description": data.get("description", "")[:100],
                })
        else:
            for node_id, data in list(G.nodes(data=True))[:Config.SAMPLE_ENTITIES_LIMIT]:
                sample_entities.append({
                    "name": data.get("name", ""),
                    "type": data.get("type", ""),
                    "description": data.get("description", "")[:100],
                })

        # Sample edges
        sample_edges = []
        for u, v, data in list(G.edges(data=True))[:Config.SEARCH_RESULT_LIMIT]:
            sample_edges.append({
                "source": G.nodes[u].get("name", u),
                "relation": data.get("relation", ""),
                "target": G.nodes[v].get("name", v),
                "fact": data.get("fact", "")[:100],
            })

        user_msg = (
            f"Graph statistics:\n{stats}\n\n"
            f"Detailed graph analysis:\n{json.dumps(detailed_graph_info, ensure_ascii=False, indent=2)}\n\n"
            f"Simulation summary:\n{sim_info}\n\n"
            f"Top entities (by connectivity):\n{json.dumps(sample_entities, ensure_ascii=False, indent=2)}\n\n"
            f"Sample relationships:\n{json.dumps(sample_edges, ensure_ascii=False, indent=2)}\n\n"
            "Create a report outline with 3-5 sections. Each section should have:\n"
            "- An analytically specific title (not generic)\n"
            "- A clear focus area\n"
            "- 2-3 key questions to investigate\n"
            "- Suggested tools to use"
        )

        messages = [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        outline = self.llm.chat_json(messages)

        # Validate / fallback
        if not outline.get("sections"):
            outline = {
                "title": "Knowledge Graph Analysis Report",
                "sections": [
                    {
                        "title": "Structural Topology and Entity Distribution",
                        "focus": "Node/edge distribution, density, clustering, entity type breakdown",
                        "key_questions": ["What is the overall graph topology?", "Which entity types dominate?", "How dense is the connectivity?"],
                        "suggested_tools": ["graph_statistics"],
                    },
                    {
                        "title": "Hub Entities and Relationship Patterns",
                        "focus": "Most connected entities, relationship type distribution, power-law analysis",
                        "key_questions": ["Which entities are central hubs?", "What relationship types are most common?", "Are there isolated clusters?"],
                        "suggested_tools": ["graph_statistics", "graph_search"],
                    },
                    {
                        "title": "Thematic Clusters and Knowledge Domains",
                        "focus": "Semantic groupings, cross-domain connections, knowledge gaps",
                        "key_questions": ["What thematic clusters emerge?", "How do domains interconnect?", "Where are the knowledge gaps?"],
                        "suggested_tools": ["graph_search", "agent_interview"],
                    },
                ],
            }

        # Ensure each section has the new fields for backward compatibility
        for section in outline.get("sections", []):
            if "key_questions" not in section:
                section["key_questions"] = []
            if "suggested_tools" not in section:
                section["suggested_tools"] = []

        return outline

    # ------------------------------------------------------------------
    # Section generation
    # ------------------------------------------------------------------

    def _generate_section(self, G: nx.DiGraph, sim_id: str, plan: dict, index: int,
                          logger: ReportLogger | None = None) -> str:
        """Generate one report section via the ReACT loop."""
        # Build section-specific system prompt if plan has key_questions
        key_questions = plan.get("key_questions", [])
        suggested_tools = plan.get("suggested_tools", [])

        if key_questions or suggested_tools:
            system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
                title=plan["title"],
                focus=plan["focus"],
                key_questions="\n".join(f"- {q}" for q in key_questions) if key_questions else "- Investigate the main aspects of this topic",
                suggested_tools=", ".join(suggested_tools) if suggested_tools else "graph_statistics, graph_search",
            )
        else:
            system_prompt = REACT_SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Generate section {index + 1}: {plan['title']}\n"
                    f"Focus: {plan['focus']}\n\n"
                    "You MUST call at least 3 tools to gather evidence before writing.\n"
                    "Cross-reference multiple sources. Then write your Final Answer "
                    "in markdown with at least 500 words of substantive analysis.\n"
                    "Cite specific data points from tool results as evidence."
                ),
            },
        ]

        return self._react_loop(messages, G, sim_id,
                                max_tools=Config.REPORT_AGENT_MAX_TOOL_CALLS,
                                min_tools=3, logger=logger)

    # ------------------------------------------------------------------
    # ReACT loop (shared by section generation and chat)
    # ------------------------------------------------------------------

    def _react_loop(self, messages: list[dict], G: nx.DiGraph,
                    simulation_id: str, max_tools: int,
                    min_tools: int = 0,
                    logger: ReportLogger | None = None) -> str:
        """Run the ReACT tool-call/observe loop until a Final Answer is produced.

        Args:
            messages: Initial message list (system + user prompt).
            G: Knowledge graph for tool execution.
            simulation_id: Simulation identifier for tool execution.
            max_tools: Maximum number of tool calls allowed.
            min_tools: Minimum tool calls before accepting a Final Answer.
                       If 0, a response without tool calls is returned as-is.
            logger: Optional ReportLogger for structured event logging.

        Returns:
            The final answer text.
        """
        tool_calls = 0
        max_iterations = 15
        iterations = 0

        while tool_calls < max_tools:
            iterations += 1
            if iterations > max_iterations:
                break

            response = self.llm.chat(messages)

            if logger:
                logger.log_event("llm_response", {"length": len(response), "iteration": iterations})

            if "Final Answer:" in response:
                return self._extract_final_answer(response)

            if "<tool_call>" in response:
                tool_name, tool_args = self._parse_tool_call(response)

                if logger:
                    logger.log_event("tool_call", {"tool": tool_name, "args": tool_args})
                    logger.log_console(f"  Tool call: {tool_name}({', '.join(tool_args)})")

                result = self._execute_tool(G, simulation_id, tool_name, tool_args)

                if logger:
                    logger.log_event("tool_result", {
                        "tool": tool_name,
                        "result_length": len(result),
                        "result_preview": result[:200],
                    })

                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"Observation: {result}"})
                tool_calls += 1
            elif min_tools == 0:
                # No tool call and no Final Answer — return the raw response
                return response
            else:
                # Nudge the LLM to use more tools or finish
                messages.append({"role": "assistant", "content": response})
                if tool_calls < min_tools:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"You've only made {tool_calls} tool call(s). "
                            f"Please call at least {min_tools} tools using "
                            "<tool_call> before writing your Final Answer."
                        ),
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": "Please provide your Final Answer:",
                    })

        # Max tools / iterations reached — force final answer
        messages.append({
            "role": "user",
            "content": (
                "You've used all tool calls. Now provide your Final Answer in markdown.\n"
                "Requirements: use ## headers, ### subsections, bullet lists, **bold** for key terms.\n"
                "Cite specific evidence from the tool results above. Minimum 500 words.\n"
                "Structure: context → findings → analysis → implications."
            ),
        })
        response = self.llm.chat(messages)
        return self._extract_final_answer(response)

    # ------------------------------------------------------------------
    # Tool parsing / execution
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_tool_call(response: str) -> tuple[str, list[str]]:
        """Extract first <tool_call>name|arg1|arg2</tool_call>."""
        match = re.search(r"<tool_call>(.*?)</tool_call>", response, re.DOTALL)
        if not match:
            return "", []
        parts = match.group(1).strip().split("|")
        name = parts[0].strip()
        args = [p.strip() for p in parts[1:]]
        return name, args

    def _execute_tool(self, G: nx.DiGraph, sim_id: str,
                      tool_name: str, tool_args: list[str]) -> str:
        """Dispatch a tool call and return its string result."""
        try:
            if tool_name == "graph_search":
                query = tool_args[0] if tool_args else ""
                return _graph_search(G, query)

            elif tool_name == "graph_statistics":
                return _graph_statistics(G)

            elif tool_name == "simulation_summary":
                return _simulation_summary(self.sim, sim_id)

            elif tool_name == "agent_interview":
                agent_id = tool_args[0] if tool_args else ""
                question = tool_args[1] if len(tool_args) > 1 else "Describe yourself."
                return _agent_interview(self.llm, self.sim, agent_id, question)

            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool error ({tool_name}): {e}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_final_answer(response: str) -> str:
        """Extract text after 'Final Answer:' marker."""
        marker = "Final Answer:"
        idx = response.find(marker)
        if idx >= 0:
            return response[idx + len(marker):].strip()
        return response.strip()

    def _assemble_report(self, outline: dict, sections: list[dict],
                         report_id: str | None = None) -> dict:
        """Build the final report dict."""
        report_id = report_id or str(uuid.uuid4())[:8]
        return {
            "id": report_id,
            "title": outline.get("title", "Report"),
            "sections": sections,
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "section_count": len(sections),
                "outline": outline,
            },
        }

    @staticmethod
    def _compute_detailed_graph_stats(G: nx.DiGraph) -> dict:
        """Compute detailed graph statistics for the planning phase."""
        info: dict = {}

        if G.number_of_nodes() == 0:
            return {"status": "empty_graph", "message": "Graph has no nodes."}

        # Top connected entities (up to 10)
        degree_sorted = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:10]
        info["top_connected_entities"] = [
            {
                "name": G.nodes[n].get("name", n),
                "type": G.nodes[n].get("type", "Unknown"),
                "connections": d,
            }
            for n, d in degree_sorted
        ]

        # Relationship type distribution
        rel_counts: dict[str, int] = {}
        for _, _, data in G.edges(data=True):
            r = data.get("relation", "UNKNOWN")
            rel_counts[r] = rel_counts.get(r, 0) + 1
        info["relationship_distribution"] = dict(
            sorted(rel_counts.items(), key=lambda x: x[1], reverse=True)
        )

        # Entity type distribution
        type_counts: dict[str, int] = {}
        for _, data in G.nodes(data=True):
            t = data.get("type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        info["entity_type_distribution"] = dict(
            sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        )

        # Connectivity metrics
        info["avg_degree"] = round(
            sum(d for _, d in G.degree()) / G.number_of_nodes(), 2
        ) if G.number_of_nodes() > 0 else 0

        # Weakly connected components (for DiGraph)
        try:
            components = list(nx.weakly_connected_components(G))
            info["connected_components"] = len(components)
            info["largest_component_size"] = max(len(c) for c in components) if components else 0
        except Exception:
            info["connected_components"] = "N/A"

        # Isolated nodes (degree 0)
        isolated = [n for n, d in G.degree() if d == 0]
        info["isolated_node_count"] = len(isolated)

        return info

    def _load_graph(self, graph_id: str = None, project_id: str = None) -> nx.DiGraph:
        """Resolve and load the NetworkX graph."""
        if graph_id and self.graph_builder:
            try:
                return self.graph_builder.load_graph(graph_id)
            except FileNotFoundError:
                pass

        if project_id:
            from app.models.project import Project
            try:
                project = Project.load(project_id)
                if project.graph_id and self.graph_builder:
                    return self.graph_builder.load_graph(project.graph_id)
            except FileNotFoundError:
                pass

        # Return empty graph as last resort
        return nx.DiGraph()
