"""Transactional, immutable case snapshots; each transition retains prior evidence."""
import copy
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .settings import DATA


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    con = sqlite3.connect(DATA / 'cases.sqlite3', timeout=30)
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('CREATE TABLE IF NOT EXISTS snapshots (case_id TEXT, revision INTEGER, body TEXT NOT NULL, PRIMARY KEY(case_id, revision))')
    return con


def create(payload):
    case = {'id': uuid.uuid4().hex, 'revision': 0, 'stage': 'C0', 'created_at': now(),
            'updated_at': now(), 'profile': payload, 'quality': None, 'discovery': None,
            'prediction': None, 'reviews': [], 'events': [{'action': 'Case created', 'at': now()}]}
    with connect() as con:
        con.execute('INSERT INTO snapshots VALUES (?, ?, ?)', (case['id'], 0, json.dumps(case)))
    return case


def get(case_id, revision=None):
    with connect() as con:
        if revision is None:
            row = con.execute('SELECT body FROM snapshots WHERE case_id=? ORDER BY revision DESC LIMIT 1', (case_id,)).fetchone()
        else:
            row = con.execute('SELECT body FROM snapshots WHERE case_id=? AND revision=?', (case_id, revision)).fetchone()
    if not row:
        raise KeyError('Case or revision not found')
    return json.loads(row[0])


def update(case_id, expected_revision, changes, action):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT body FROM snapshots WHERE case_id=? ORDER BY revision DESC LIMIT 1', (case_id,)).fetchone()
        if not row:
            raise KeyError('Case not found')
        case = json.loads(row[0])
        if case['revision'] != expected_revision:
            raise ValueError('This case changed in another window. Reload before saving.')
        case.update(copy.deepcopy(changes))
        case['revision'] += 1
        case['updated_at'] = now()
        case['events'].append({'action': action, 'at': now(), 'revision': case['revision']})
        con.execute('INSERT INTO snapshots VALUES (?, ?, ?)', (case_id, case['revision'], json.dumps(case, allow_nan=False)))
    return case


def list_cases():
    with connect() as con:
        rows = con.execute('SELECT body FROM snapshots s WHERE revision=(SELECT MAX(revision) FROM snapshots WHERE case_id=s.case_id) ORDER BY rowid DESC').fetchall()
    return [json.loads(r[0]) for r in rows]


def history(case_id):
    with connect() as con:
        rows = con.execute('SELECT body FROM snapshots WHERE case_id=? ORDER BY revision', (case_id,)).fetchall()
    return [json.loads(r[0]) for r in rows]
