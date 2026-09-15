from datetime import datetime, timezone
import traceback
import yaml

from core.models import UserQuery, RequestType, Persona, DualResponse
from core.intent_extractor import IntentExtractor
from core.context_builder import ContextBuilder
from core.sql_generator import SQLGenerator
from core.sql_reviewer import SQLReviewer
from core.dual_synthesizer import DualSynthesizer
from ports.logger_port import LoggerPort, LogEntry
from core.policy_gate import PolicyGate


class Orchestrator:
    def __init__(self, intent_extractor, context_builder, sql_generator,
                 sql_validator, sql_executor, dual_synthesizer, logger, policy_path,
                 sql_reviewer=None):
        self.intent_extractor = intent_extractor
        self.context_builder = context_builder
        self.sql_generator = sql_generator
        self.sql_validator = sql_validator
        self.sql_executor = sql_executor
        self.dual_synthesizer = dual_synthesizer
        self.logger = logger
        self.sql_reviewer = sql_reviewer
        with open(policy_path, encoding="utf-8") as f:
            self.policies = yaml.safe_load(f) or {}
        self.policy_gate = PolicyGate(self.policies)

    def process(self, query: UserQuery) -> DualResponse:
        trace_id = query.session_id
        self._log(trace_id, "REQUEST_RECEIVED", {"query": query.text, "user_id": query.user_id, "role": query.user_role})
        try:
            decision = self.policy_gate.authorize_query(query.user_role)
            if not decision.allowed:
                return self._error_response(trace_id, decision.reason)
            intent = self.intent_extractor.extract(query)
            self._log(trace_id, "INTENT_EXTRACTED", {
                "category": intent.category,
                "query_type": intent.query_type,
                "confidence": intent.confidence,
                "entities": intent.entities,
                "relevant_tables": intent.relevant_tables,
            })

            if intent.needs_clarification:
                return DualResponse(RequestType.CLARIFICATION, None, None, None,
                                     intent.clarification_question or "Please clarify your request.",
                                     intent.confidence, trace_id)

            min_confidence = float(self.policies.get("min_confidence", 0.70))
            if intent.confidence < min_confidence:
                return self._error_response(trace_id, "Request confidence is too low to execute safely.")

            context = self.context_builder.build(intent)
            self._log(trace_id, "CONTEXT_BUILT", {
                "tables": [t.get("name") for t in context.get("tables", [])],
                "business_context_count": len(context.get("business_context", [])),
            })

            generated = self.sql_generator.generate(intent, context)
            self._log(trace_id, "SQL_GENERATED", {
                "sql": generated.sql,
                "metric": generated.metric_used,
                "dimensions": generated.dimensions,
                "filters": generated.filters,
            })

            if self.sql_reviewer and SQLReviewer.should_review(intent, generated, context):
                review = self.sql_reviewer.review(query.text, intent, generated, context)
                self._log(trace_id, "SQL_REVIEWED", review.model_dump())

                if not review.approved:
                    revised = SQLReviewer.revised_intent(intent, review)
                    if revised.category == intent.category and revised.entities == intent.entities:
                        issues_msg = "; ".join(review.issues) or "unspecified semantic mismatch"
                        return self._error_response(
                            trace_id,
                            "SQL semantic review rejected the query: " + issues_msg,
                        )
                    self._log(trace_id, "INTENT_REVISED_FROM_REVIEW", {
                        "previous_category": intent.category,
                        "new_category": revised.category,
                        "previous_entities": intent.entities,
                        "new_entities": revised.entities,
                    })
                    intent = revised
                    context = self.context_builder.build(intent)
                    generated = self.sql_generator.generate(intent, context)
                    self._log(trace_id, "SQL_REGENERATED", {
                        "sql": generated.sql,
                        "metric": generated.metric_used,
                        "dimensions": generated.dimensions,
                        "filters": generated.filters,
                    })

                    second_review = self.sql_reviewer.review(query.text, intent, generated, context)
                    self._log(trace_id, "SQL_REVIEWED_AFTER_REGENERATION", second_review.model_dump())
                    if not second_review.approved:
                        issues_msg = "; ".join(second_review.issues) or "unspecified semantic mismatch"
                        return self._error_response(
                            trace_id,
                            "SQL semantic review rejected the regenerated query: " + issues_msg,
                        )
            elif self.sql_reviewer:
                self._log(trace_id, "SQL_REVIEW_SKIPPED", {"reason": "simple_low_risk_query"})

            validation = self.sql_validator.validate(generated.sql)
            self._log(trace_id, "SQL_VALIDATED", {
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "tables_accessed": validation.tables_accessed,
            })
            if not validation.is_valid:
                return self._error_response(trace_id, f"Invalid SQL: {'; '.join(validation.errors)}")
            table_policy = self.policy_gate.validate_tables(validation.tables_accessed)
            if not table_policy.allowed:
                return self._error_response(trace_id, table_policy.reason)

            allowed_rows = int(self.policies.get("max_rows_returned", 1000))
            timeout_ms = int(self.policies.get("query_timeout_ms", 10000))
            execution = self.sql_executor.execute(generated.sql, readonly=True, timeout_ms=timeout_ms)
            self._log(trace_id, "SQL_EXECUTED", {
                "success": execution.success,
                "row_count": execution.row_count,
                "execution_time_ms": execution.execution_time_ms,
                "error": execution.error,
            })
            if not execution.success:
                return self._error_response(trace_id, f"Execution error: {execution.error}")
            if execution.row_count > allowed_rows:
                return self._error_response(trace_id, "Result exceeds the configured maximum row count.")

            ba = self.dual_synthesizer.synthesize(Persona.BUSINESS_ANALYST, query.text, generated.sql, execution.rows or [], context)
            ceo = self.dual_synthesizer.synthesize(Persona.CEO, query.text, generated.sql, execution.rows or [], context)
            self._log(trace_id, "RESPONSE_READY", {"rows": execution.row_count, "execution_time_ms": execution.execution_time_ms})
            return DualResponse(RequestType.SQL_WITH_RAG if context["business_context"] else RequestType.SQL_ONLY,
                                 generated.sql, ba, ceo, None, intent.confidence, trace_id)
        except Exception as exc:
            self._log(trace_id, "INTERNAL_ERROR", {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
            return self._error_response(trace_id, "An internal error occurred.")

    def _error_response(self, trace_id, message):
        self._log(trace_id, "ERROR", {"message": message})
        return DualResponse(RequestType.REJECTED, None, None, None, message, 0.0, trace_id)

    def _log(self, trace_id, event, payload):
        self.logger.log(LogEntry(trace_id, datetime.now(timezone.utc), event, payload))
