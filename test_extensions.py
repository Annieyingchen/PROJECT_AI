"""运行 python test_extensions.py；使用临时数据库和模拟模型，无 API 调用。"""
import json
import sys
import tempfile
import types
from pathlib import Path
import extensions

with tempfile.TemporaryDirectory() as directory:
    extensions.DB_PATH = Path(directory) / 'extensions.sqlite3'
    initial = extensions.snapshot()
    assert len(initial['plugins']) == 4
    skill = extensions.save_skill({'name': '编辑', 'description': '测试技能', 'prompt': '保留原意，输出修改说明。', 'enabled': True})
    assert extensions.resolve(skill['id'])['prompt'].startswith('保留原意')
    extensions.toggle('skill', skill['id'], False)
    try:
        extensions.resolve(skill['id'])
        raise AssertionError('disabled skill resolved')
    except ValueError:
        pass
    extensions.toggle('skill', skill['id'], True)
    extensions.toggle('plugin', 'calculator', False)
    extensions.toggle('plugin', 'knowledge', False)
    active = extensions.resolve(skill['id'])
    assert active['tool_names'] == ['get_current_time'] and not active['knowledge']
    try:
        extensions.toggle('plugin', 'unknown', True)
        raise AssertionError('unknown plugin accepted')
    except ValueError:
        pass
    extensions.save_skill({**skill, 'name': '编辑新版', 'description': '更新测试', 'prompt': '更新后的提示词', 'enabled': True})
    assert extensions.resolve(skill['id'])['prompt'] == '更新后的提示词'
    calls = []
    def chat(messages):
        calls.append(messages)
        return '完成'
    def raw(messages, tools):
        calls.append(tools)
        if len(calls) == 1:
            return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': '1', 'function': {'name': 'calculator', 'arguments': '{"expression":"2+2"}'}}]}
        assert '未启用' in messages[-1]['content']
        return {'content': '完成'}
    sys.modules['llm'] = types.SimpleNamespace(chat=chat, chat_raw=raw)
    import qa
    import memory
    qa.ask(memory.ConversationMemory(), '问题', skill_prompt='测试提示')
    assert any('测试提示' in m['content'] for m in calls[0])
    calls.clear()
    qa.ask_with_tools(memory.ConversationMemory(), '问题', tool_names=active['tool_names'])
    assert [t['function']['name'] for t in calls[0]] == ['get_current_time']
    calls.clear()
    qa.ask_with_tools(memory.ConversationMemory(), '问题', tool_names=[])
    assert calls[0][0]['role'] == 'system'
    extensions.delete_skill(skill['id'])
    assert not extensions.snapshot()['skills']
print('PASS: skill CRUD, persistence, disabled skill rejection, plugin gates, prompt injection, disabled tool execution blocked, no-tool fallback')
