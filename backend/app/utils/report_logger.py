"""Structured logging for report generation."""

import json
import os
from datetime import datetime


class ReportLogger:
    """Logs report generation events to JSONL and plain-text files.

    Each report gets its own directory under ``<data_dir>/reports/<report_id>/``
    containing:
      - ``agent_log.jsonl`` -- structured event stream (one JSON object per line)
      - ``console_log.txt`` -- human-readable timestamped messages

    Event types:
        report_start, planning_start, planning_complete,
        section_start, tool_call, tool_result, llm_response,
        section_complete, report_complete
    """

    def __init__(self, report_id: str, data_dir: str):
        self.report_dir = os.path.join(data_dir, "reports", report_id)
        os.makedirs(self.report_dir, exist_ok=True)
        self.agent_log_path = os.path.join(self.report_dir, "agent_log.jsonl")
        self.console_log_path = os.path.join(self.report_dir, "console_log.txt")

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def log_event(self, event_type: str, data: dict | None = None):
        """Append a structured event to ``agent_log.jsonl``."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data or {},
        }
        with open(self.agent_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_console(self, message: str):
        """Append a human-readable line to ``console_log.txt``."""
        ts = datetime.now().strftime("%H:%M:%S")
        with open(self.console_log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_agent_log(self, from_line: int = 0) -> list[dict]:
        """Read agent log entries starting from *from_line* (0-based).

        Returns a list of parsed JSON objects.
        """
        if not os.path.exists(self.agent_log_path):
            return []
        with open(self.agent_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        entries = []
        for line in lines[from_line:]:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append({"raw": line})
        return entries

    def get_console_log(self, from_line: int = 0) -> list[str]:
        """Read console log lines starting from *from_line* (0-based).

        Returns a list of raw text lines.
        """
        if not os.path.exists(self.console_log_path):
            return []
        with open(self.console_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [l.rstrip("\n") for l in lines[from_line:]]
