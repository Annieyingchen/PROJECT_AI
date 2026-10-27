"""本地 SQLite 个人知识库；中英文关键词 / 字符二元组检索，无新增依赖。"""
import json
import math
import re
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DB_PATH = Path(__file__).with_name('knowledge.sqlite3')


@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, name TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)')
    try:
        with db:
            yield db
    finally:
        db.close()


def list_documents():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT id, name, length(content) AS characters, created_at FROM documents ORDER BY created_at DESC')]


def add_document(name, content):
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError('文档名称需为 1–120 字')
    if not isinstance(content, str) or not content.strip() or len(content.encode('utf-8')) > 200000:
        raise ValueError('文档不能为空，且需小于 200 KB')
    doc = {'id': uuid4().hex, 'name': name.strip(), 'content': content.strip(), 'created_at': datetime.now(timezone.utc).isoformat()}
    with connect() as db:
        count, total = db.execute('SELECT count(*), coalesce(sum(length(content)), 0) FROM documents').fetchone()
        if count >= 100 or total + len(content) > 3000000:
            raise ValueError('知识库已达容量上限（100 篇 / 300 万字）')
        db.execute('INSERT INTO documents VALUES (:id, :name, :content, :created_at)', doc)
    return {k: v for k, v in doc.items() if k != 'content'}


def get_document(doc_id):
    with connect() as db:
        row = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
        return dict(row) if row else None


def delete_document(doc_id):
    with connect() as db:
        return db.execute('DELETE FROM documents WHERE id = ?', (doc_id,)).rowcount > 0


def tokens(text):
    words = re.findall(r'[a-z0-9_]+', text.lower())
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        words.extend(run[i:i+2] for i in range(len(run)-1))
        if len(run) == 1:
            words.append(run)
    return Counter(words)


def search(query, limit=4):
    q = tokens(query)
    if not q:
        return []
    chunks = []
    with connect() as db:
        for doc in db.execute('SELECT id, name, content FROM documents'):
            for start in range(0, len(doc['content']), 620):
                excerpt = doc['content'][start:start+800]
                terms = tokens(doc['name'] + ' ' + excerpt)
                chunks.append((doc['id'], doc['name'], start, excerpt, terms))
    frequency = Counter()
    for *_, terms in chunks:
        frequency.update(terms.keys())
    results = []
    for doc_id, name, start, excerpt, terms in chunks:
        score = sum((1 + math.log((1+len(chunks))/(1+frequency[t])))*min(terms[t], 3) for t in q if t in terms)
        if score:
            score /= math.sqrt(max(1, sum(terms.values())))
            results.append({'id': doc_id, 'name': name, 'offset': start, 'excerpt': excerpt, 'score': score})
    return sorted(results, key=lambda r: r['score'], reverse=True)[:limit]


def context(sources):
    if not sources:
        return ''
    return json.dumps([{'source': i, 'name': s['name'], 'text': s['excerpt']} for i, s in enumerate(sources, 1)], ensure_ascii=False)
