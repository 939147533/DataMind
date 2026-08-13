# -*- coding: utf-8 -*-
path = r"E:\Code\DataMind\backend\app\routers\charts.py"
src = open(path, encoding="utf-8").read()

# 1) 增加 JSON 安全序列化 helper（放在 _chart_out 前）
old = '''def _chart_out(c: Chart) -> dict:'''
new = '''def _json_safe(value):
    """将数据库返回的值转换为 JSON 可序列化类型（datetime/Decimal 等）。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            return float(value)
    except ImportError:  # pragma: no cover
        pass
    return str(value)


def _serialize_rows(rows: list) -> list:
    return [[_json_safe(v) for v in row] for row in rows]


def _chart_out(c: Chart) -> dict:'''
assert old in src
src = src.replace(old, new, 1)

# 2) _chart_with_data 序列化 rows
old = '''            columns, rows = _run_query(ds, chart.sql_text)
            out["columns"] = columns
            out["rows"] = rows'''
new = '''            columns, rows = _run_query(ds, chart.sql_text)
            out["columns"] = columns
            out["rows"] = _serialize_rows(rows)'''
assert old in src
src = src.replace(old, new, 1)

# 3) chart_data 接口序列化 rows
old = '''    columns, rows = _run_query(ds, chart.sql_text)
    return JSONResponse(content=ok({"columns": columns, "rows": rows}), headers={"Cache-Control": "no-cache, must-revalidate"})'''
new = '''    columns, rows = _run_query(ds, chart.sql_text)
    return JSONResponse(
        content=ok({"columns": columns, "rows": _serialize_rows(rows)}),
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )'''
assert old in src
src = src.replace(old, new, 1)

open(path, "w", encoding="utf-8").write(src)
print("charts.py patched OK")