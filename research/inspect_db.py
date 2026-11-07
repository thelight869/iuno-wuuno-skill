import json
import os
from pathlib import Path

import duckdb

DB = os.environ.get("DB_PATH", "ashare_pit.duckdb")
OUT = Path(os.environ.get("OUT_DIR", "output"))
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(DB, read_only=True)
objects = con.execute(
    """
    SELECT table_schema, table_name, table_type
    FROM information_schema.tables
    WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
    ORDER BY table_schema, table_name
    """
).fetchall()

report = {"database": DB, "objects": []}
lines = ["# DuckDB schema inspection", ""]

for schema, name, obj_type in objects:
    qname = f'"{schema}"."{name}"'
    cols = con.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, name],
    ).fetchall()
    try:
        count = con.execute(f"SELECT COUNT(*) FROM {qname}").fetchone()[0]
    except Exception:
        count = None
    try:
        cur = con.execute(f"SELECT * FROM {qname} LIMIT 3")
        names = [d[0] for d in cur.description]
        sample = [dict(zip(names, row)) for row in cur.fetchall()]
        sample = [{k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in row.items()} for row in sample]
    except Exception as exc:
        sample = [{"error": str(exc)}]

    entry = {
        "schema": schema,
        "name": name,
        "type": obj_type,
        "row_count": count,
        "columns": [{"name": c, "type": t, "nullable": n} for c, t, n in cols],
        "sample": sample,
    }
    report["objects"].append(entry)

    lines += [f"## {schema}.{name}", f"- type: {obj_type}", f"- rows: {count:,}" if isinstance(count, int) else "- rows: unknown", "", "| column | type | nullable |", "|---|---|---|"]
    for c, t, n in cols:
        lines.append(f"| {c} | {t} | {n} |")
    lines += ["", "```json", json.dumps(sample, ensure_ascii=False, indent=2, default=str), "```", ""]

(OUT / "schema.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
(OUT / "schema.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[:300]))
