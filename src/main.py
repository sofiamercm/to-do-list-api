"""to-do-list-api: a small To-Do List API backed by PostgreSQL on AWS RDS."""
import json
import os
from datetime import datetime, timezone

import boto3
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="to-do-list-api")

# Settings come from environment variables, never from hardcoded values.
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DB_SECRET_NAME = os.getenv("DB_SECRET_NAME", "to-do-list-api/db-credentials")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE
)
"""


class TaskCreate(BaseModel):
    """The JSON body that POST /tasks accepts."""
    title: str
    completed: bool = False


def get_db_credentials():
    """Ask AWS Secrets Manager for the database credentials (at runtime)."""
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    response = client.get_secret_value(SecretId=DB_SECRET_NAME)
    return json.loads(response["SecretString"])


def get_connection():
    """Open a connection to PostgreSQL and make sure the tasks table exists."""
    creds = get_db_credentials()
    conn = psycopg2.connect(
        host=creds["host"],
        port=creds.get("port", 5432),
        dbname=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
        connect_timeout=5,
    )
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn


@app.get("/tasks")
def list_tasks():
    """Return all registered tasks."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, completed FROM tasks ORDER BY id")
            rows = cur.fetchall()
        return [{"id": r[0], "title": r[1], "completed": r[2]} for r in rows]
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn is not None:
            conn.close()


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    """Create a task and store it in PostgreSQL."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (title, completed) VALUES (%s, %s) RETURNING id",
                (task.title, task.completed),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
        return {"id": new_id, "title": task.title, "completed": task.completed}
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn is not None:
            conn.close()


@app.get("/version")
def get_version():
    """Return the deployed version, read from the APP_VERSION variable."""
    return {"version": os.getenv("APP_VERSION", "unknown")}


@app.get("/health")
def health():
    """Check the database connection and report status, version and time."""
    db_status = "OK"
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        db_status = "FAIL"
    finally:
        if conn is not None:
            conn.close()
    return {
        "database": db_status,
        "version": os.getenv("APP_VERSION", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }