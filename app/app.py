import os
import socket
from pathlib import Path

import psycopg
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
VERSION = os.getenv("APP_VERSION", "cp1")
NODE = os.getenv("NODE_NAME", socket.gethostname())


def connect():
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=5432,
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=3,
    )


@app.get("/health")
def health():
    try:
        if Path("/app/UNHEALTHY").exists():
            raise RuntimeError("Intentional lab health fault")
        with connect() as db:
            db.execute("SELECT 1").fetchone()
        return jsonify(status="ok", node=NODE, version=VERSION), 200
    except Exception:
        app.logger.exception("Health check failed")
        return jsonify(status="unhealthy", node=NODE, version=VERSION), 503


@app.get("/api/records")
def records():
    with connect() as db:
        rows = db.execute(
            "SELECT id,title,status FROM records ORDER BY id"
        ).fetchall()
    return jsonify(
        node=NODE,
        version=VERSION,
        records=[dict(id=r[0], title=r[1], status=r[2]) for r in rows],
    )


@app.post("/api/records")
def create():
    data = request.get_json(silent=True) or request.form
    title = str(data.get("title", "")).strip()
    if not 1 <= len(title) <= 120:
        return jsonify(error="title must be 1 to 120 characters"), 400
    with connect() as db:
        row = db.execute(
            "INSERT INTO records(title) VALUES (%s) RETURNING id",
            (title,),
        ).fetchone()
    app.logger.warning("Created mock record id=%s node=%s", row[0], NODE)
    return jsonify(id=row[0], node=NODE, version=VERSION), 201


@app.patch("/api/records/<int:record_id>")
def update(record_id):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in ("open", "closed"):
        return jsonify(error="status must be open or closed"), 400
    with connect() as db:
        row = db.execute(
            "UPDATE records SET status=%s WHERE id=%s RETURNING id",
            (status, record_id),
        ).fetchone()
    if row:
        return jsonify(id=row[0], status=status), 200
    return jsonify(error="not found"), 404


@app.delete("/api/records/<int:record_id>")
def delete(record_id):
    with connect() as db:
        row = db.execute(
            "DELETE FROM records WHERE id=%s RETURNING id",
            (record_id,),
        ).fetchone()
    app.logger.warning("Delete mock record id=%s node=%s", record_id, NODE)
    if row:
        return jsonify(deleted=row[0]), 200
    return jsonify(error="not found"), 404


@app.get("/")
def home():
    with connect() as db:
        rows = db.execute(
            "SELECT id,title,status FROM records ORDER BY id"
        ).fetchall()
    return render_template_string(
        """<!doctype html>
        <title>OPS Demo Portal</title>
        <h1>OPS Demo Portal</h1>
        <p>Mock data only | {{node}} | {{version}}</p>
        <table border="1">
        <tr><th>ID</th><th>Title</th><th>Status</th></tr>
        {% for r in rows %}
        <tr><td>{{r[0]}}</td><td>{{r[1]}}</td><td>{{r[2]}}</td></tr>
        {% endfor %}
        </table>
        <p>Use /api/records for the read write demonstration.</p>""",
        rows=rows,
        node=NODE,
        version=VERSION,
    )
