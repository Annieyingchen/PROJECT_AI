"""工作台技能与插件注册表；仅支持声明式提示词技能，不运行上传代码。"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

DB_PATH = Path(__file__).with_name('extensions.sqlite3')
BUILTINS = [
    {'id': 'drawing', 'name': 'AI 绘图', 'description': '将画面描述发送给独立配置的图片模型，生成并下载图片。', 'kind': 'drawing', 'capability': 'drawing'},
    {'id': 'calculator', 'name': '精确计算', 'description': '通过 Agent 调用计算器执行数学表达式。', 'kind': 'tool', 'capability': 'calculator'},
    {'id': 'clock', 'name': '本地时间', 'description': '读取运行工作台的电脑日期与时间。', 'kind': 'tool', 'capability': 'get_current_time'},
    {'id': 'knowledge', 'name': '个人知识库', 'description': '检索本地文档，将相关片段发送给已配置的模型。', 'kind': 'knowledge', 'capability': 'knowledge'},
]


@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, prompt TEXT NOT NULL, enabled INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS plugins (id TEXT PRIMARY KEY, enabled INTEGER NOT NULL)')
            for plugin in BUILTINS:
                db.execute('INSERT OR IGNORE INTO plugins VALUES (?, 1)', (plugin['id'],))
            yield db
    finally:
        db.close()


def snapshot():
    with connect() as db:
        flags = {row['id']: bool(row['enabled']) for row in db.execute('SELECT * FROM plugins')}
        skills = [dict(row) for row in db.execute('SELECT * FROM skills ORDER BY rowid DESC')]
        for skill in skills:
            skill['enabled'] = bool(skill['enabled'])
        return {'plugins': [{**p, 'enabled': flags[p['id']]} for p in BUILTINS], 'skills': skills}


def save_skill(data):
    if not isinstance(data, dict):
        raise ValueError('技能格式错误')
    for field, maximum in [('name', 60), ('description', 240), ('prompt', 8000)]:
        if not isinstance(data.get(field), str) or not data[field].strip() or len(data[field]) > maximum:
            raise ValueError('请填写技能名称、描述和提示词（上限 60 / 240 / 8000 字）')
    if not isinstance(data.get('enabled', True), bool):
        raise ValueError('启用状态格式错误')
    skill_id = data.get('id')
    with connect() as db:
        if skill_id is not None:
            if not isinstance(skill_id, str) or not db.execute('SELECT 1 FROM skills WHERE id=?', (skill_id,)).fetchone():
                raise ValueError('技能不存在')
        else:
            if db.execute('SELECT count(*) FROM skills').fetchone()[0] >= 50:
                raise ValueError('最多保存 50 个技能')
            skill_id = uuid4().hex
        db.execute('INSERT OR REPLACE INTO skills VALUES (?, ?, ?, ?, ?)', (skill_id, data['name'].strip(), data['description'].strip(), data['prompt'].strip(), int(data.get('enabled', True))))
    return {'id': skill_id}


def toggle(kind, item_id, enabled):
    if kind not in ('skill', 'plugin') or not isinstance(item_id, str) or not isinstance(enabled, bool):
        raise ValueError('启用状态格式错误')
    if kind == 'plugin' and item_id not in {p['id'] for p in BUILTINS}:
        raise ValueError('插件不存在')
    with connect() as db:
        table = 'skills' if kind == 'skill' else 'plugins'
        if not db.execute(f'UPDATE {table} SET enabled=? WHERE id=?', (int(enabled), item_id)).rowcount:
            raise ValueError('扩展不存在')
    return {'updated': True}


def delete_skill(item_id):
    if not isinstance(item_id, str):
        raise ValueError('技能 ID 格式错误')
    with connect() as db:
        if not db.execute('DELETE FROM skills WHERE id=?', (item_id,)).rowcount:
            raise ValueError('技能不存在')
    return {'deleted': True}


def resolve(skill_id=None):
    state = snapshot()
    plugins = {p['id']: p for p in state['plugins']}
    prompt = ''
    if skill_id:
        selected = next((s for s in state['skills'] if s['id'] == skill_id and s['enabled']), None)
        if selected is None:
            raise ValueError('所选技能已停用或删除，请重新选择')
        prompt = selected['prompt']
    return {'prompt': prompt, 'tool_names': [p['capability'] for p in plugins.values() if p['enabled'] and p['kind'] == 'tool'], 'knowledge': plugins['knowledge']['enabled']}
