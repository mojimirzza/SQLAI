"""
Enriched Orchestrator — Memory + Baseline Edition
--------------------------------------------------
Combines Zero-Mem historical context with Baseline Enrichment.
Pipeline:
  Query → Memory Intent → SQL Gen → Review → Execute → Baseline Enrich → Synthesize → Save Memory
"""
import uuid
from datetime import datetime, timezone

from core.models import UserQuery, RequestType, Persona, DualResponse, Intent, GeneratedSQL
from core.orchestrator import Orchestrator
from core.baseline_models import BaselineMetrics
from core.baseline_enricher import BaselineEnricher
from ports.memory_store_port import MemoryStorePort, QueryRecord
from core.policy_gate import PolicyGate


class EnrichedOrchestrator:
    """
    Wraps base Orchestrator with both Zero-Mem and Baseline Enrichment.
    """

    def __init__(self, base_orchestrator: Orchestrator,
                 memory_store: MemoryStorePort,
                 baseline_enricher: BaselineEnricher, policy_gate: PolicyGate | None = None):
        self._base = base_orchestrator
        self.memory_store = memory_store
        self.baseline_enricher = baseline_enricher
        self.policy_gate = policy_gate or PolicyGate(base_orchestrator.policies)

    def process(self, query: UserQuery) -> DualResponse:
        trace_id = query.session_id
        self._base._log(trace_id, "REQUEST_RECEIVED", {
            "query": query.text,
            "user_id": query.user_id,
            "role": query.user_role,
            "session_id": query.session_id,
        })

        intent: Intent | None = None
        generated: GeneratedSQL | None = None
        execution = None
        baseline: BaselineMetrics | None = None

        try:
            # 0. Deterministic role authorization before any warehouse work
            policy = self.policy_gate.authorize_query(query.user_role)
            if not policy.allowed:
                response = self._base._error_response(trace_id, policy.reason)
                self._save_record(query, None, None, None, response, baseline)
                return response

            # 1. Intent extraction (memory-aware)
            intent = self._base.intent_extractor.extract(query)
            self._base._log(trace_id, "INTENT_EXTRACTED", {
                "category": intent.category,
                "query_type": intent.query_type,
                "confidence": intent.confidence,
                "entities": intent.entities,
                "relevant_tables": intent.relevant_tables,
            })

            if intent.needs_clarification:
                response = DualResponse(
                    RequestType.CLARIFICATION, None, None, None,
                    intent.clarification_question or "Please clarify your request.",
                    intent.confidence, trace_id
                )
                self._save_record(query, intent, None, None, response, baseline)
                return response

            min_confidence = float(self._base.policies.get("min_confidence", 0.70))
            if intent.confidence < min_confidence:
                response = self._base._error_response(trace_id, "Request confidence is too low to execute safely.")
                self._save_record(query, intent, None, None, response, baseline)
                return response

            # 2. Context build
            context = self._base.context_builder.build(intent)
            self._base._log(trace_id, "CONTEXT_BUILT", {
                "tables": [t.get("name") for t in context.get("tables", [])],
                "business_context_count": len(context.get("business_context", [])),
            })

            # 3. SQL generation
            generated = self._base.sql_generator.generate(intent, context)
            self._base._log(trace_id, "SQL_GENERATED", {
                "sql": generated.sql,
                "metric": generated.metric_used,
                "dimensions": generated.dimensions,
                "filters": generated.filters,
                "joins": [{"table": j.table, "type": j.type} for j in generated.joins],
            })

            # 4. SQL Review
            if self._base.sql_reviewer and hasattr(self._base.sql_reviewer, 'should_review'):
                from core.sql_reviewer import SQLReviewer
                if SQLReviewer.should_review(intent, generated, context):
                    review = self._base.sql_reviewer.review(query.text, intent, generated, context)
                    self._base._log(trace_id, "SQL_REVIEWED", review.model_dump())

                    if not review.approved:
                        revised = SQLReviewer.revised_intent(intent, review)
                        if revised.category == intent.category and revised.entities == intent.entities:
                            issues_msg = "; ".join(review.issues) or "unspecified semantic mismatch"
                            response = self._base._error_response(
                                trace_id,
                                "SQL semantic review rejected the query: " + issues_msg,
                            )
                            self._save_record(query, intent, generated, None, response, baseline)
                            return response
                        self._base._log(trace_id, "INTENT_REVISED_FROM_REVIEW", {
                            "previous_category": intent.category,
                            "new_category": revised.category,
                        })
                        intent = revised
                        context = self._base.context_builder.build(intent)
                        generated = self._base.sql_generator.generate(intent, context)
                        self._base._log(trace_id, "SQL_REGENERATED", {
                            "sql": generated.sql,
                            "metric": generated.metric_used,
                        })

                        second_review = self._base.sql_reviewer.review(query.text, intent, generated, context)
                        self._base._log(trace_id, "SQL_REVIEWED_AFTER_REGENERATION", second_review.model_dump())
                        if not second_review.approved:
                            issues_msg = "; ".join(second_review.issues) or "unspecified semantic mismatch"
                            response = self._base._error_response(
                                trace_id,
                                "SQL semantic review rejected the regenerated query: " + issues_msg,
                            )
                            self._save_record(query, intent, generated, None, response, baseline)
                            return response
                else:
                    self._base._log(trace_id, "SQL_REVIEW_SKIPPED", {"reason": "simple_low_risk_query"})

            # 5. Validation
            validation = self._base.sql_validator.validate(generated.sql)
            self._base._log(trace_id, "SQL_VALIDATED", {
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "tables_accessed": validation.tables_accessed,
            })
            if not validation.is_valid:
                response = self._base._error_response(trace_id, f"Invalid SQL: {'; '.join(validation.errors)}")
                self._save_record(query, intent, generated, None, response, baseline)
                return response
            table_policy = self.policy_gate.validate_tables(validation.tables_accessed)
            if not table_policy.allowed:
                response = self._base._error_response(trace_id, table_policy.reason)
                self._save_record(query, intent, generated, None, response, baseline)
                return response

            # 6. Execution
            allowed_rows = int(self._base.policies.get("max_rows_returned", 1000))
            timeout_ms = int(self._base.policies.get("query_timeout_ms", 10000))
            execution = self._base.sql_executor.execute(generated.sql, readonly=True, timeout_ms=timeout_ms)
            self._base._log(trace_id, "SQL_EXECUTED", {
                "success": execution.success,
                "row_count": execution.row_count,
                "execution_time_ms": execution.execution_time_ms,
                "error": execution.error,
            })

            if not execution.success:
                response = self._base._error_response(trace_id, f"Execution error: {execution.error}")
                self._save_record(query, intent, generated, execution, response, baseline)
                return response
            if execution.row_count > allowed_rows:
                response = self._base._error_response(trace_id, "Result exceeds the configured maximum row count.")
                self._save_record(query, intent, generated, execution, response, baseline)
                return response

            # 7. BASELINE ENRICHMENT (NEW)
            baseline = self.baseline_enricher.enrich(intent, generated, execution)
            self._base._log(trace_id, "BASELINE_ENRICHED", {
                "current_value": baseline.current_value,
                "yesterday_delta_pct": baseline.yesterday_delta_pct,
                "avg_30d_delta_pct": baseline.avg_30d_delta_pct,
                "anomaly_flag": baseline.anomaly_flag,
                "anomaly_severity": baseline.anomaly_severity,
            })

            # 8. Synthesis with baseline context
            from core.baseline_synthesizer import BaselineAwareDualSynthesizer
            synth = BaselineAwareDualSynthesizer(self._base.dual_synthesizer.llm)
            ba = synth.synthesize(
                Persona.BUSINESS_ANALYST, query.text, generated.sql,
                execution.rows or [], context, baseline
            )
            ceo = synth.synthesize(
                Persona.CEO, query.text, generated.sql,
                execution.rows or [], context, baseline
            )

            response = DualResponse(
                RequestType.SQL_WITH_RAG if context.get("business_context") else RequestType.SQL_ONLY,
                generated.sql, ba, ceo, None, intent.confidence, trace_id
            )

            # Persist once before optional sidecar hooks so they have a stable query id.
            record = self._save_record(query, intent, generated, execution, response, baseline)

            # Trigger sidecar follow-up suggestions off the primary response path.
            try:
                from core.sidecar_bridge import trigger_suggest_async
                trigger_suggest_async(record.id)
                self._base._log(trace_id, "SIDECAR_SUGGESTION_TRIGGERED", {"async": True})
            except Exception:
                pass  # Sidecar is optional; never fail the main query

            # Trigger sidecar anomaly investigation if anomaly flagged
            if baseline and baseline.anomaly_flag and baseline.anomaly_severity in ("medium", "high"):
                try:
                    from core.sidecar_bridge import trigger_investigate
                    trigger_investigate(record.id, async_run=True)
                    self._base._log(trace_id, "SIDECAR_INVESTIGATION_TRIGGERED", {
                        "anomaly_severity": baseline.anomaly_severity,
                    })
                except Exception:
                    pass

            self._base._log(trace_id, "RESPONSE_READY", {
                "rows": execution.row_count,
                "execution_time_ms": execution.execution_time_ms,
                "baseline_anomaly": baseline.anomaly_flag,
            })

            return response

        except Exception as exc:
            import traceback
            self._base._log(trace_id, "INTERNAL_ERROR", {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
            response = self._base._error_response(trace_id, "An internal error occurred.")
            try:
                self._save_record(query, intent, generated, execution, response, baseline)
            except:
                pass
            return response

    def _save_record(self, query: UserQuery, intent: Intent | None,
                    generated: GeneratedSQL | None, execution,
                    response: DualResponse, baseline: BaselineMetrics | None):
        """Save raw query record + baseline snapshot. No LLM summarization."""
        record = QueryRecord(
            id=str(uuid.uuid4()),
            user_id=query.user_id,
            session_id=query.session_id,
            query_text=query.text,
            timestamp=datetime.now(timezone.utc),
            intent_category=intent.category if intent else "",
            intent_query_type=intent.query_type if intent else "aggregate",
            intent_entities=intent.entities if intent else {},
            generated_sql=generated.sql if generated else "",
            sql_metric=generated.metric_used if generated else None,
            sql_dimensions=generated.dimensions if generated else [],
            sql_filters=generated.filters if generated else [],
            sql_joins=[{"table": j.table, "type": j.type, "on": j.on} for j in generated.joins] if generated else [],
            execution_row_count=getattr(execution, 'row_count', 0) if execution else 0,
            execution_success=getattr(execution, 'success', False) if execution else False,
            response_type=response.request_type.value,
            confidence=response.confidence,
        )
        self.memory_store.save(record)
        self._base._log(query.session_id, "MEMORY_SAVED", {
            "record_id": record.id,
            "baseline_anomaly": baseline.anomaly_flag if baseline else None,
        })
        return record
