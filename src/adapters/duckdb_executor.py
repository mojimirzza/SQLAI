from __future__ import annotations

import threading
import time

import duckdb

from ports.sql_executor_port import SQLExecutorPort, ExecutionResult


class DuckDBExecutor(SQLExecutorPort):
    """Read-only DuckDB executor with a real Python-side timeout guard.

    DuckDB versions/environments may differ in statement-timeout support.  A
    watchdog therefore calls the connection's interrupt() method so the
    timeout contract remains meaningful without depending on a particular
    DuckDB SQL setting.
    """

    def __init__(self, db_path=":memory:"):
        self.db_path = db_path

    def execute(self, sql, readonly=True, timeout_ms=30000):
        start = time.monotonic()
        conn = None
        timer = None
        timed_out = False

        def interrupt() -> None:
            nonlocal timed_out
            timed_out = True
            if conn is not None:
                try:
                    conn.interrupt()
                except Exception:
                    # The query result/error is still collected by the main
                    # thread; this callback must never escape its thread.
                    pass

        try:
            conn = duckdb.connect(self.db_path, read_only=readonly)
            if timeout_ms and timeout_ms > 0:
                timer = threading.Timer(timeout_ms / 1000.0, interrupt)
                timer.daemon = True
                timer.start()

            result = conn.execute(sql)
            columns = [d[0] for d in (result.description or [])]
            rows = result.fetchmany(1001)
            if len(rows) > 1000:
                rows = rows[:1001]
            data = [dict(zip(columns, row)) for row in rows]

            if timed_out:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return ExecutionResult(
                    False, None, None, 0, elapsed_ms,
                    f"Query timeout exceeded ({timeout_ms} ms)"
                )

            return ExecutionResult(
                True,
                data,
                columns,
                len(data),
                int((time.monotonic() - start) * 1000),
                None,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if timed_out:
                return ExecutionResult(
                    False, None, None, 0, elapsed_ms,
                    f"Query timeout exceeded ({timeout_ms} ms)"
                )
            return ExecutionResult(False, None, None, 0, elapsed_ms, str(exc))
        finally:
            if timer is not None:
                timer.cancel()
            if conn:
                conn.close()
