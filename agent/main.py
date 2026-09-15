"""
Agent Scheduler
Runs the alert agent on a schedule.
Uses APScheduler if available, falls back to schedule library,
falls back to simple time.sleep loop.
"""
import os
import sys
import time
from datetime import datetime

# Add parent to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent_loop import run_agent_cycle


# Configuration
DB_PATH = os.environ.get("AGENT_DB_PATH", "data/bank.duckdb")
ALERT_DB_PATH = os.environ.get("AGENT_ALERT_DB", "data/agent_alerts.db")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", None)
INTERVAL_MINUTES = int(os.environ.get("AGENT_INTERVAL_MIN", "15"))


def run_once():
    """Run a single agent cycle."""
    try:
        run_agent_cycle(db_path=DB_PATH, slack_webhook=SLACK_WEBHOOK)
    except Exception as e:
        print(f"ERROR: Agent cycle failed: {e}")
        import traceback
        traceback.print_exc()


def run_with_apscheduler():
    """Preferred: APScheduler with background execution."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_once,
            trigger=IntervalTrigger(minutes=INTERVAL_MINUTES),
            id="alert_agent",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300
        )
        scheduler.start()

        print(f"Agent started with APScheduler (every {INTERVAL_MINUTES} min)")
        print(f"DB: {DB_PATH}")
        print(f"Slack: {'enabled' if SLACK_WEBHOOK else 'disabled (console fallback)'}")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.shutdown()
            print("\nAgent stopped.")

    except ImportError:
        print("APScheduler not installed. Trying schedule library...")
        run_with_schedule()


def run_with_schedule():
    """Fallback: schedule library."""
    try:
        import schedule

        schedule.every(INTERVAL_MINUTES).minutes.do(run_once)

        print(f"Agent started with schedule library (every {INTERVAL_MINUTES} min)")
        print("Press Ctrl+C to stop\n")

        while True:
            schedule.run_pending()
            time.sleep(1)

    except ImportError:
        print("schedule library not installed. Using simple sleep loop...")
        run_with_sleep()


def run_with_sleep():
    """Last resort: simple time.sleep loop. No persistence, no overlap protection."""
    print(f"Agent started with sleep loop (every {INTERVAL_MINUTES} min)")
    print("WARNING: No overlap protection. No persistence.\n")

    while True:
        run_once()
        print(f"Sleeping {INTERVAL_MINUTES} minutes...\n")
        time.sleep(INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    # Run immediately once, then schedule
    print("=" * 50)
    print("ALERT AGENT")
    print("=" * 50)
    run_once()
    run_with_apscheduler()
