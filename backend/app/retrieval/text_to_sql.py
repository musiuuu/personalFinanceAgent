"""NL → SQL over the transaction store.

The LLM generates SQL against a fixed, documented schema; the guard
(sql_guard.py) validates it and the query runs on a read-only connection.
The prompt is a convenience — the guard is the security boundary.
"""
from pydantic import BaseModel

from ..config import get_settings
from .sql_guard import SQLGuardError, run_readonly

SCHEMA_DOC = """
TABLE "transaction" (
  id INTEGER PRIMARY KEY,
  account_id INTEGER,
  txn_date DATE,            -- ISO yyyy-mm-dd
  amount_minor INTEGER,     -- money in PAISA (1 PKR = 100), SIGNED: negative = spend/outflow
  currency TEXT,            -- 'PKR'
  raw_description TEXT,
  merchant_normalized TEXT, -- cleaned merchant, e.g. 'NETFLIX'
  category TEXT,            -- one of: INCOME, SALARY, TRANSFER_IN, TRANSFER_OUT, GROCERIES,
                            -- DINING, TRANSPORT, FUEL, UTILITIES, RENT, SUBSCRIPTIONS, SHOPPING,
                            -- HEALTH, EDUCATION, TRAVEL, ENTERTAINMENT, FEES_CHARGES,
                            -- CASH_WITHDRAWAL, OTHER
  balance_after_minor INTEGER,
  is_recurring BOOLEAN, is_anomaly BOOLEAN
)
TABLE account (id, name, currency, opening_balance_minor, opening_balance_date)
TABLE document (id, filename, file_type, status, statement_period_start, statement_period_end,
                opening_balance_minor, closing_balance_minor)
TABLE budget (id, category, monthly_limit_minor)
TABLE goal (id, name, target_amount_minor, target_date, saved_so_far_minor)
""".strip()

_PROMPT = """You translate questions about personal finances into a single SQLite SELECT query.

Schema:
{schema}

Rules:
- Output ONLY the SQL, no prose, no code fences.
- SELECT only. Single statement. Note the table name "transaction" needs double quotes.
- Money is stored in minor units (paisa). For PKR figures, SELECT amount_minor/100.0 AS amount_pkr.
- Outflows are negative; use ABS() and amount_minor < 0 when the user asks about spending.
- Dates are ISO strings; use strftime('%Y-%m', txn_date) for month grouping.

Question: {question}
SQL:"""


class SQLQueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list]
    error: str | None = None


def generate_sql(question: str) -> str:
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError(
            "NL→SQL needs ANTHROPIC_API_KEY; set it in backend/.env."
        )
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_cheap_model,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": _PROMPT.format(schema=SCHEMA_DOC, question=question),
            }
        ],
    )
    sql = response.content[0].text.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.removeprefix("sql").strip()
    return sql


def answer_with_sql(question: str, db_path: str) -> SQLQueryResult:
    sql = generate_sql(question)
    try:
        columns, rows = run_readonly(db_path, sql)
        return SQLQueryResult(
            sql=sql, columns=columns, rows=[list(r) for r in rows]
        )
    except SQLGuardError as e:
        return SQLQueryResult(sql=sql, columns=[], rows=[], error=str(e))
