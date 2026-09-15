import sqlglot
from sqlglot import exp
from ports.sql_validator_port import SQLValidatorPort, ValidationResult

class SQLGlotValidator(SQLValidatorPort):
    def validate(self, sql):
        try:
            parsed = sqlglot.parse_one(sql, read="duckdb")
        except Exception as exc:
            return ValidationResult(False, [f"Parse error: {exc}"], None, [], True)
        errors = []
        if not isinstance(parsed, exp.Select):
            errors.append("Only a single SELECT statement is allowed.")
        if ";" in sql.strip().rstrip(";"):
            errors.append("Multiple SQL statements are not allowed.")
        tables = [t.name for t in parsed.find_all(exp.Table)]
        destructive_types = (exp.Delete, exp.Insert, exp.Update, exp.Create, exp.Drop, exp.Alter, exp.TruncateTable)
        if any(isinstance(parsed, t) for t in destructive_types):
            errors.append("Destructive SQL is not allowed.")
        return ValidationResult(not errors, errors,
                                parsed.key if isinstance(parsed, exp.Select) else type(parsed).__name__,
                                tables, bool(errors and "Destructive" in " ".join(errors)))
