"""
Objective Definer
Decides: alert / suppress / escalate / log_only
Simple rule engine. Structured for future LLM upgrade.
"""
from dataclasses import dataclass


@dataclass
class Objective:
    action: str          # "alert" | "suppress" | "escalate" | "log_only"
    severity: str        # "low" | "medium" | "high" | "critical"
    channel: str         # "#ops-alerts" | "#ops-critical" | "#daily-summary"
    reasoning: str       # human-readable why
    suppress_reason: str | None = None  # if suppressed, why


def define_objective(anomaly: dict, in_maintenance: bool) -> Objective:
    """
    Given an anomaly row and maintenance status, decide what to do.

    Rules (ordered by priority):
    1. Maintenance window → SUPPRESS
    2. SLA breach + anomaly → HIGH alert
    3. Z-score > 3.0 → MEDIUM alert
    4. Z-score 1.5-3.0 → LOW alert (daily summary)
    5. Single metric, no SLA, low z-score → LOG_ONLY
    """

    metric = anomaly.get("metric_name", "unknown")
    z_score = anomaly.get("z_score") or 0
    is_sla = anomaly.get("is_sla_breach", 0)
    severity_db = anomaly.get("anomaly_severity", "none")

    # Rule 1: Maintenance window
    if in_maintenance:
        return Objective(
            action="suppress",
            severity="low",
            channel="#daily-summary",
            reasoning=f"{metric} anomalous but server in maintenance window",
            suppress_reason="maintenance_window"
        )

    # Rule 2: SLA breach
    if is_sla:
        return Objective(
            action="alert",
            severity="high",
            channel="#ops-critical",
            reasoning=f"{metric} SLA breach detected. Immediate attention required."
        )

    # Rule 3: High z-score
    if abs(z_score) > 3.0:
        return Objective(
            action="alert",
            severity="medium",
            channel="#ops-alerts",
            reasoning=f"{metric} z-score {z_score:+.2f} indicates significant deviation."
        )

    # Rule 4: Medium z-score
    if abs(z_score) > 1.5:
        return Objective(
            action="alert",
            severity="low",
            channel="#daily-summary",
            reasoning=f"{metric} z-score {z_score:+.2f} shows moderate deviation."
        )

    # Rule 5: Everything else → log only
    return Objective(
        action="log_only",
        severity="low",
        channel="#daily-summary",
        reasoning=f"{metric} anomaly detected but within acceptable range (z-score {z_score:+.2f})."
    )
