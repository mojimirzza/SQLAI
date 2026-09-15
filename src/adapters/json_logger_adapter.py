import json, sys
from ports.logger_port import LoggerPort, LogEntry
class JSONLoggerAdapter(LoggerPort):
    def log(self, entry):
        print(json.dumps({
            "trace_id": entry.trace_id, "timestamp": entry.timestamp.isoformat(),
            "event": entry.event, "payload": entry.payload
        }, ensure_ascii=False, default=str), file=sys.stderr, flush=True)
