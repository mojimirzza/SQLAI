"""
Gap Analyst Agent — Mode: report
Analyzes query history to find missing metrics/dimensions in the semantic layer.
Outputs a Markdown report for human review.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any

from core.db_reader import DBReader
from core.llm_client import LLMClient
from core.state_manager import StateManager
from core.tool_registry import tool


class GapAnalyst:
    """Agent that reads memory.db and semantic_layer.yaml, produces gap reports."""

    def __init__(self, db: DBReader, llm: LLMClient, state: StateManager,
                 lookback_days: int = 7, min_confidence: float = 0.70,
                 min_query_count: int = 3, reports_dir: str = "./reports"):
        self.db = db
        self.llm = llm
        self.state = state
        self.lookback_days = lookback_days
        self.min_confidence = min_confidence
        self.min_query_count = min_query_count
        self.reports_dir = reports_dir

    def run(self) -> dict:
        """Execute the gap analysis and produce a report."""
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        # 1. Gather data
        low_conf_queries = self.db.get_recent_queries(
            days=self.lookback_days,
            min_confidence=0.0,  # get all, filter later
        )
        semantic_layer = self.db.get_semantic_layer()
        existing_metrics = set(self.db.list_metrics())
        existing_dimensions = set(self.db.list_dimensions())

        # 1b. Gather alert patterns
        alert_history = self.db.get_alert_history(days=self.lookback_days)
        alert_metrics = set(a.get("metric_name", "") for a in alert_history if a.get("metric_name"))

        # 2. Build the analysis prompt
        prompt = self._build_prompt(low_conf_queries, existing_metrics, existing_dimensions, alert_metrics, len(alert_history))

        # 3. LLM analysis
        schema = {
            "type": "object",
            "properties": {
                "missing_metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metric names users asked for but don't exist",
                },
                "missing_dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dimension names users asked for but don't exist",
                },
                "low_confidence_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Themes of low-confidence queries",
                },
                "suggested_yaml_snippets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Draft YAML for top missing metrics",
                },
                "estimated_impact": {
                    "type": "string",
                    "description": "How many queries would be improved",
                },
            },
            "required": ["missing_metrics", "missing_dimensions", "low_confidence_themes"],
        }

        with open("prompts/gap_analyst_system.md", encoding="utf-8") as f:
            system = f.read()

        result = self.llm.generate(prompt, system=system, schema=schema)

        # 4. Generate report
        report_path = self._write_report(result, low_conf_queries)

        # 5. Save state
        self.state.save_gap_report(
            report_id=run_id,
            report_date=datetime.now().strftime("%Y-%m-%d"),
            report_path=report_path,
            missing_metrics=result.get("missing_metrics", []),
            missing_dimensions=result.get("missing_dimensions", []),
        )
        self.state.log_run(
            run_id=run_id, agent_name="GapAnalyst", mode="report",
            started_at=started_at, finished_at=datetime.now(),
            success=True, output_summary=f"Report: {report_path}",
        )

        return {
            "report_path": report_path,
            "missing_metrics": result.get("missing_metrics", []),
            "missing_dimensions": result.get("missing_dimensions", []),
            "run_id": run_id,
        }

    def _build_prompt(self, queries: list[dict], existing_metrics: set[str],
                      existing_dimensions: set[str], alert_metrics: set[str] | None = None,
                      alert_count: int = 0) -> str:
        # Filter to low-confidence and problematic queries
        alert_metrics = alert_metrics or set()
        problematic = [q for q in queries if q.get("confidence", 1.0) < self.min_confidence]

        query_samples = []
        for q in problematic[:30]:
            query_samples.append(
                f"- Query: '{q.get('query_text', '')}' | "
                f"Category: {q.get('intent_category', 'unknown')} | "
                f"Confidence: {q.get('confidence', 0):.2f} | "
                f"Type: {q.get('response_type', 'unknown')}"
            )

        return f"""Analyze the following query history from a Text-to-SQL transaction monitoring system.

EXISTING METRICS IN SEMANTIC LAYER:
{chr(10).join(f"- {m}" for m in sorted(existing_metrics))}

EXISTING DIMENSIONS IN SEMANTIC LAYER:
{chr(10).join(f"- {d}" for d in sorted(existing_dimensions))}

ALERT AGENT PATTERNS (last {self.lookback_days} days):
Metrics that triggered alerts: {alert_metrics}
Total alerts: {alert_count}

PROBLEMATIC QUERIES (low confidence or rejected/clarification):
Total count: {len(problematic)}
{chr(10).join(query_samples)}

Identify what users are asking for that the system cannot answer. Focus on:
1. Metrics that don't exist in the semantic layer
2. Dimensions that don't exist
3. Common themes in failed/low-confidence queries
4. Draft YAML snippets for the most impactful additions
"""

    def _write_report(self, result: dict, queries: list[dict]) -> str:
        from pathlib import Path
        Path(self.reports_dir).mkdir(parents=True, exist_ok=True)

        filename = f"gap_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = Path(self.reports_dir) / filename

        lines = [
            "# Coverage Gap Analysis Report",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Lookback:** {self.lookback_days} days",
            f"**Total queries analyzed:** {len(queries)}",
            "",
            "## Missing Metrics",
        ]
        for m in result.get("missing_metrics", []):
            lines.append(f"- {m}")
        if not result.get("missing_metrics"):
            lines.append("_No missing metrics identified._")

        lines.extend(["", "## Missing Dimensions"])
        for d in result.get("missing_dimensions", []):
            lines.append(f"- {d}")
        if not result.get("missing_dimensions"):
            lines.append("_No missing dimensions identified._")

        lines.extend(["", "## Low-Confidence Query Themes"])
        for t in result.get("low_confidence_themes", []):
            lines.append(f"- {t}")

        lines.extend(["", "## Suggested YAML Snippets"])
        for snippet in result.get("suggested_yaml_snippets", []):
            lines.extend(["```yaml", snippet, "```", ""])

        lines.extend(["", "## Estimated Impact", result.get("estimated_impact", "N/A")])

        filepath.write_text("\\n".join(lines), encoding="utf-8")
        return str(filepath)
