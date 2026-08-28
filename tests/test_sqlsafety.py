"""agent/sqlsafety 只读校验单测: 只放行安全的单条只读 SQL, 其余一律拒绝。"""

from agent.sqlsafety import MAX_LIMIT, enforce_max_rows, sanitize_statement, validate_readonly

# ---------- 只读放行 ----------


def test_allows_simple_select():
    ok, err = validate_readonly("SELECT * FROM stock_analysis LIMIT 10")
    assert ok, err


def test_allows_case_insensitive_and_quotes():
    ok, err = validate_readonly("SELECT close, name FROM stock_analysis WHERE code='600519' LIMIT 5")
    assert ok, err


def test_allows_with_cte():
    ok, err = validate_readonly("WITH x AS (SELECT code FROM stock_analysis LIMIT 3) SELECT * FROM x LIMIT 3")
    assert ok, err


def test_strips_trailing_semicolons():
    ok, err = validate_readonly("SELECT * FROM stock_analysis LIMIT 10;")
    assert ok, err
    assert sanitize_statement("SELECT 1;;;") == "SELECT 1"


# ---------- 只写/危险操作一律拒绝 ----------


def test_rejects_all_mutations():
    for sql in [
        "INSERT INTO stock_analysis VALUES(1)",
        "UPDATE stock_analysis SET close=0 WHERE code='600519'",
        "DELETE FROM stock_analysis",
        "DROP TABLE stock_analysis",
        "ALTER TABLE stock_analysis ADD COLUMN x TEXT",
        "CREATE TABLE foo (id int)",
        "REPLACE INTO stock_analysis VALUES(1)",
        "TRUNCATE TABLE stock_analysis",
        "ATTACH DATABASE 'evil.db' AS e",
        "DETACH DATABASE e",
        "VACUUM",
        "PRAGMA database_list",
        "REINDEX stock_analysis",
        "COMMIT",
        "ROLLBACK",
    ]:
        ok, _ = validate_readonly(sql)
        assert not ok, f"应当拒绝: {sql}"


def test_rejects_non_select_lead():
    ok, _ = validate_readonly("WITHOUT SELECT")
    assert not ok


# ---------- 危险函数 ----------


def test_rejects_dangerous_functions():
    for sql in [
        "SELECT readfile('/etc/passwd') LIMIT 1",
        "SELECT writefile('/tmp/x', 'y') LIMIT 1",
        "SELECT load_extension('/tmp/evil.so') LIMIT 1",
        "SELECT glob('*') FROM stock_analysis LIMIT 1",
    ]:
        ok, _ = validate_readonly(sql)
        assert not ok, f"应当拒绝危险函数: {sql}"


# ---------- LIMIT 约束 ----------


def test_requires_limit():
    ok, err = validate_readonly("SELECT * FROM stock_analysis")
    assert not ok
    assert "LIMIT" in err


def test_rejects_limit_over_max():
    ok, _ = validate_readonly(f"SELECT * FROM stock_analysis LIMIT {MAX_LIMIT + 1}")
    assert not ok


def test_accepts_limit_at_max():
    ok, err = validate_readonly(f"SELECT * FROM stock_analysis LIMIT {MAX_LIMIT}")
    assert ok, err


# ---------- 多语句/注释规避 ----------


def test_rejects_multiple_statements():
    ok, err = validate_readonly("SELECT 1; SELECT 2")
    assert not ok, "内部出现分号应拒绝"
    assert "单条" in err


def test_comment_does_not_bypass_blocklist():
    # 注释被剥掉后 DROP 仍会被检测
    ok, _ = validate_readonly("SELECT 1 -- okay\n; DROP TABLE stock_analysis -- x\nLIMIT 1")
    assert not ok


def test_empty_sql_rejected():
    ok, _ = validate_readonly("   ")
    assert not ok


# ---------- enforce_max_rows ----------


def test_enforce_max_rows_truncates():
    rows = [{"i": i} for i in range(250)]
    out, truncated = enforce_max_rows(rows, limit=200)
    assert len(out) == 200 and truncated is True


def test_enforce_max_rows_noop_when_small():
    rows = [{"i": i} for i in range(5)]
    out, truncated = enforce_max_rows(rows, limit=200)
    assert out == rows and truncated is False
