"""The security boundary for NL→SQL.

The guard — not the prompt — is what makes text_to_sql safe:
- single statement, SELECT-only
- forbidden keyword blacklist (INSERT/UPDATE/DELETE/DROP/PRAGMA/ATTACH/...)
- table whitelist
- LIMIT auto-injected (capped at 500)
- executed on a READ-ONLY SQLite connection, so even a guard bug cannot write
"""
import re
import sqlite3

MAX_LIMIT = 500

ALLOWED_TABLES = {"account", "document", "transaction", "budget", "goal"}

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|pragma|attach|detach|"
    r"vacuum|reindex|truncate|grant|revoke)\b",
    re.I,
)
# Identifiers after FROM/JOIN/INTO etc.
_TABLE_REF = re.compile(r"\b(?:from|join)\s+[\"'`\[]?([a-zA-Z_][a-zA-Z0-9_]*)", re.I)
_HAS_LIMIT = re.compile(r"\blimit\s+(\d+)\b", re.I)


class SQLGuardError(ValueError):
    pass


def _strip_strings_and_comments(sql: str) -> str:
    """Remove string literals and comments so keyword checks can't be smuggled
    past inside quotes, and comment-based obfuscation fails."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)
    return sql


def guard_sql(sql: str) -> str:
    """Validate and normalize a model-generated query. Raises SQLGuardError."""
    candidate = sql.strip().rstrip(";").strip()
    if not candidate:
        raise SQLGuardError("Empty query.")
    if ";" in candidate:
        raise SQLGuardError("Multiple statements are not allowed.")

    stripped = _strip_strings_and_comments(candidate)
    first_word = stripped.split(None, 1)[0].lower() if stripped.split() else ""
    if first_word not in ("select", "with"):
        raise SQLGuardError("Only SELECT queries are allowed.")
    if _FORBIDDEN.search(stripped):
        raise SQLGuardError("Query contains a forbidden keyword.")

    # CTE names are legal "tables"; collect them before whitelisting.
    cte_names = {
        m.group(1).lower()
        for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", stripped, re.I)
    }
    for m in _TABLE_REF.finditer(stripped):
        table = m.group(1).lower()
        if table not in ALLOWED_TABLES and table not in cte_names:
            raise SQLGuardError(f"Table '{table}' is not in the whitelist.")

    if m := _HAS_LIMIT.search(stripped):
        if int(m.group(1)) > MAX_LIMIT:
            candidate = _HAS_LIMIT.sub(f"LIMIT {MAX_LIMIT}", candidate)
    else:
        candidate = f"{candidate} LIMIT {MAX_LIMIT}"
    return candidate


def run_readonly(db_path: str, sql: str) -> tuple[list[str], list[tuple]]:
    """Execute a guarded query against a read-only SQLite connection."""
    safe_sql = guard_sql(sql)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.execute(safe_sql)
        columns = [c[0] for c in cursor.description or []]
        return columns, cursor.fetchall()
    finally:
        conn.close()
