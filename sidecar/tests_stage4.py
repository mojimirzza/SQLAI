from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "sidecar"))
from core.sql_guard import SidecarSQLGuard

class V:
    def validate(self, sql):
        class R: pass
        r=R(); r.is_valid=sql.strip().upper().startswith("SELECT"); r.errors=[] if r.is_valid else ["not select"]; r.tables_accessed=["fact_transaction"]
        return r

def test_guard_allows_select():
    assert SidecarSQLGuard(V(), {"fact_transaction"}).check("SELECT * FROM fact_transaction").allowed

def test_guard_blocks_non_select():
    assert not SidecarSQLGuard(V(), {"fact_transaction"}).check("DELETE FROM fact_transaction").allowed


def test_state_manager_records_iteration_trace(tmp_path):
    from core.state_manager import StateManager
    from core.loop_engineering import LoopVerifier, LoopEvaluator, LoopReplay
    state = StateManager(str(tmp_path / "agent_state.db"))
    state.start_iteration("r1", "i1", 1, "query_warehouse", {"sql": "SELECT 1"}, "Need evidence")
    state.finish_iteration("i1", {"status": "ok", "rows": [{"x": 1}]}, "ok", "passed", "tool returned status=ok")
    state.start_iteration("r1", "i2", 2, "finish", {}, "Evidence is enough")
    state.finish_iteration("i2", {"answer": "done"}, "ok", "passed", "agent explicitly declared completion", termination_reason="agent_finish")
    trace = state.get_run_iterations("r1")
    assert [x["iteration_no"] for x in trace] == [1, 2]
    assert LoopVerifier().verify_trace(trace).status == "passed"
    assert LoopEvaluator().evaluate(trace)["passed"] is True
    assert len(LoopReplay().replay(trace)) == 2


def test_react_agent_changes_action_after_observation(tmp_path):
    import json
    from types import SimpleNamespace
    from core.agent import ReActAgent
    from core.tool_registry import Tool
    from core.state_manager import StateManager

    class FakeLLM:
        def __init__(self):
            self.calls = 0
        def chat(self, messages, tools=None, tool_choice="auto"):
            self.calls += 1
            if self.calls == 1:
                args = {"thought": "Need evidence", "purpose": "check", "sql": "SELECT 1"}
                name = "query_warehouse"
            else:
                args = {"thought": "Evidence is enough", "answer": '{"hypothesis":"supported","confidence":"high","next_action":"review"}'}
                name = "finish"
            call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args), name=name), id="c1")
            msg = SimpleNamespace(tool_calls=[call], content="")
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    state = StateManager(str(tmp_path / "agent_state.db"))
    llm = FakeLLM()
    tool = Tool("query_warehouse", "test", {"purpose": {"type": "string"}, "sql": {"type": "string"}}, lambda purpose, sql: {"rows": [{"ok": 1}]})
    result = ReActAgent(llm, [tool], max_steps=3).run("test", "system", run_id="r1", state=state, investigation_id="inv1")
    trace = state.get_run_iterations("r1")
    assert result.success
    assert [x["decision_action"] for x in trace] == ["query_warehouse", "finish"]
    assert trace[0]["verification_status"] == "passed"
    assert trace[-1]["termination_reason"] == "agent_finish"
