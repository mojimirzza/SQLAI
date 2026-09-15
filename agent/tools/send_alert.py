"""
Tool: send_alert
Synthesizes and sends alert notification.
"""
from agent.notifiers.slack_adapter import SlackAdapter


def send_alert(
    anomaly: dict,
    severity: str,
    channel: str,
    slack_webhook: str | None = None
) -> dict:
    """
    Synthesize alert message and send to notification channel.

    Returns: {"sent": bool, "message": str, "channel": str}
    """
    # Build message
    metric = anomaly.get("metric_name", "unknown")
    current = anomaly.get("current_value", "N/A")
    server = anomaly.get("server_sk", "all")
    yest_delta = anomaly.get("yest_delta_pct")
    avg7_delta = anomaly.get("avg_7d_delta_pct")
    z_score = anomaly.get("z_score")
    is_sla = anomaly.get("is_sla_breach", 0)

    lines = [
        f"🚨 *{severity.upper()} Alert: {metric}*",
        f"Server: SW{server}" if server and server != "all" else "Server: All",
        f"Current: {current:,.2f}" if isinstance(current, (int, float)) else f"Current: {current}",
    ]

    if yest_delta is not None:
        emoji = "📉" if yest_delta < 0 else "📈"
        lines.append(f"vs Yesterday: {yest_delta:+.1f}% {emoji}")

    if avg7_delta is not None:
        lines.append(f"vs 7-Day Avg: {avg7_delta:+.1f}%")

    if z_score is not None:
        lines.append(f"Z-Score: {z_score:+.2f}")

    if is_sla:
        lines.append("⚠️ *SLA BREACH DETECTED*")

    message = "\n".join(lines)

    # Send
    sent = False
    if slack_webhook:
        notifier = SlackAdapter(slack_webhook)
        sent = notifier.send(channel, message)

    return {
        "sent": sent,
        "message": message,
        "channel": channel,
        "severity": severity,
    }
