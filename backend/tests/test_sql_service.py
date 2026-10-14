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


def test_classify_hardening():
    """首关键字会被写操作绕过的写法必须提升等级，字符串/注释里的关键字不能误判。"""
    # WITH 的主动词可能是写操作
    assert classify_statement("WITH x AS (SELECT 1) DELETE FROM t") == "DML"
    assert classify_statement("WITH x AS (SELECT 1), y AS (SELECT 2) UPDATE t SET a = 1") == "DML"
    assert classify_statement("WITH x AS (SELECT 1) CREATE TABLE y AS SELECT 1") == "DDL"
    assert classify_statement("WITH RECURSIVE x AS (SELECT 1) SELECT * FROM x") == "READ"
    # EXPLAIN ANALYZE 会真正执行被解释的语句
    assert classify_statement("EXPLAIN ANALYZE DELETE FROM t") == "DML"
    assert classify_statement("EXPLAIN (ANALYZE, BUFFERS) DELETE FROM t") == "DML"
    assert classify_statement("EXPLAIN ANALYZE SELECT 1") == "READ"
    assert classify_statement("EXPLAIN PLAN FOR DELETE FROM t") == "READ"
    # 只读语句里隐含加锁 / 建表 / 写文件
    assert classify_statement("SELECT * FROM t FOR UPDATE") == "DML"
    assert classify_statement("SELECT * FROM t LOCK IN SHARE MODE") == "DML"
    assert classify_statement("SELECT * FROM t INTO OUTFILE '/tmp/x'") == "DDL"
    assert classify_statement("SELECT * FROM t INTO new_table") == "DDL"
    # 字面量与注释中的关键字不参与分类
    assert classify_statement("SELECT * FROM t WHERE note = 'for update'") == "READ"
    assert classify_statement("SELECT * FROM t WHERE note = 'into'") == "READ"
    assert classify_statement("SELECT /* for update */ 1") == "READ"
    assert classify_statement("SELECT 'a''b' FROM t") == "READ"
    # 括号开头 / 无法识别的语句
    assert classify_statement("(SELECT 1) UNION (SELECT 2)") == "READ"
    assert classify_statement("FOO BAR") == "DML"


def test_format_sql():
    formatted = format_sql("select id,name from users where age>18 order by id")
    assert "SELECT" in formatted.upper()
    assert "FROM" in formatted.upper()
