"""Small persistent workspace store. All writes are serialized, including workers."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

DATA = Path(os.environ.get('CUTLINE_DATA_DIR', Path(__file__).resolve().parents[1] / '.data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()

@contextmanager
def connection():
    con = sqlite3.connect(DATA / 'workspace.sqlite3')
    try:
        with con:
            con.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            yield con
    finally:
        # sqlite3's own context manager commits but does not close the handle.
        # Explicit closure matters for repeated polling and Windows file locks.
        con.close()

def save(job):
    with LOCK, connection() as con:
        con.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?)', (job['id'], json.dumps(job)))
    return job

def get(job_id):
    with LOCK, connection() as con:
        row = con.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
    return json.loads(row[0]) if row else None

def update(job_id, **changes):
    with LOCK:
        job = get(job_id)
        if job:
            job.update(changes)
            save(job)
        return job

def update_clip(job_id, clip_id, **changes):
    with LOCK:
        job = get(job_id)
        if job:
            for clip in job['clips']:
                if clip['id'] == clip_id:
                    clip.update(changes)
                    save(job)
                    return clip
    return None

def all_jobs():
    with LOCK, connection() as con:
        rows = con.execute('SELECT payload FROM jobs ORDER BY rowid DESC').fetchall()
    return [json.loads(row[0]) for row in rows]

def delete(job_id):
    with LOCK, connection() as con:
        con.execute('DELETE FROM jobs WHERE id=?', (job_id,))
