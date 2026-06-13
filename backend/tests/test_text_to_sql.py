"""Adversarial tests for the SQL guard — the security boundary of NL→SQL."""
import sqlite3

import pytest

from app.retrieval.sql_guard import SQLGuardError, guard_sql, run_readonly

REJECTED = [
    "DELETE FROM \"transaction\"",
    "delete from \"transaction\" where 1=1",
    "DROP TABLE goal",
    "INSERT INTO budget (category, monthly_limit_minor) VALUES ('DINING', 1)",
    "UPDATE \"transaction\" SET amount_minor = 0",
    "PRAGMA writable_schema = 1",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "SELECT * FROM \"transaction\"; DROP TABLE goal",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM users",
    "CREATE TABLE pwned (id int)",
    "WITH x AS (SELECT 1) UPDATE goal SET name='x'",
    "SELECT 1 /* sneaky */ ; DELETE FROM goal",
]


@pytest.mark.parametrize("sql", REJECTED)
def test_guard_rejects(sql):
    with pytest.raises(SQLGuardError):
        guard_sql(sql)


ACCEPTED = [
    'SELECT * FROM "transaction" WHERE category = \'DINING\'',
    'SELECT SUM(amount_minor)/100.0 FROM "transaction" WHERE amount_minor < 0',
    "SELECT name, target_amount_minor FROM goal",
    'WITH monthly AS (SELECT strftime(\'%Y-%m\', txn_date) m, SUM(amount_minor) s '
    'FROM "transaction" GROUP BY m) SELECT * FROM monthly',
]


@pytest.mark.parametrize("sql", ACCEPTED)
def test_guard_accepts_and_injects_limit(sql):
    guarded = guard_sql(sql)
    assert "LIMIT" in guarded.upper()


def test_guard_caps_existing_limit():
    guarded = guard_sql('SELECT * FROM "transaction" LIMIT 999999')
    assert "LIMIT 500" in guarded


def test_guard_keeps_modest_limit():
    guarded = guard_sql('SELECT * FROM "transaction" LIMIT 10')
    assert "LIMIT 10" in guarded


def test_keyword_inside_string_literal_is_fine():
    guarded = guard_sql(
        "SELECT * FROM \"transaction\" WHERE raw_description = 'DROP SHIPMENT DELETE LTD'"
    )
    assert "LIMIT" in guarded


def test_readonly_connection_blocks_writes_even_if_guard_failed(tmp_path):
    """Defense in depth: even raw writes fail on the ro connection."""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE goal (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO goal (name) VALUES ('Laptop')")
    conn.commit()
    conn.close()

    cols, rows = run_readonly(str(db), "SELECT name FROM goal")
    assert rows == [("Laptop",)]

    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO goal (name) VALUES ('pwned')")
    ro.close()
