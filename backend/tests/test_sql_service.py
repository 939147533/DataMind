"""SQL 拆分/分类/格式化测试。"""
from app.services.sql_service import classify_statement, format_sql, split_statements


def test_split_simple():
    stmts = split_statements("SELECT 1; SELECT 2")
    assert stmts == ["SELECT 1", "SELECT 2"]


def test_split_with_quotes_and_comments():
    sql = "SELECT 'a;b' AS x; -- comment; here\nSELECT 2 /* block; comment */;"
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert "a;b" in stmts[0]
    assert "SELECT 2" in stmts[1]


def test_split_single_no_semicolon():
    assert split_statements("SELECT 1") == ["SELECT 1"]


def test_classify():
    assert classify_statement("SELECT * FROM users") == "READ"
    assert classify_statement("SHOW TABLES") == "READ"
    assert classify_statement("EXPLAIN SELECT 1") == "READ"
    assert classify_statement("WITH t AS (SELECT 1) SELECT * FROM t") == "READ"
    assert classify_statement("INSERT INTO t VALUES (1)") == "DML"
    assert classify_statement("UPDATE t SET a=1") == "DML"
    assert classify_statement("DELETE FROM t") == "DML"
    assert classify_statement("CREATE TABLE t(id int)") == "DDL"
    assert classify_statement("ALTER TABLE t ADD c int") == "DDL"
    assert classify_statement("DROP TABLE t") == "DDL"
    assert classify_statement("TRUNCATE TABLE t") == "DDL"


def test_format_sql():
    formatted = format_sql("select id,name from users where age>18 order by id")
    assert "SELECT" in formatted.upper()
    assert "FROM" in formatted.upper()
