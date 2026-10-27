"""AI 工作台：python workbench.py；复用现有问答和记忆层。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import config
import memory
import knowledge
import extensions
from urllib.parse import urlsplit, parse_qs


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/extensions':
            return self.send_json(200, extensions.snapshot())
        if url.path == '/api/knowledge':
            return self.send_json(200, {'documents': knowledge.list_documents()})
        if url.path == '/api/knowledge/document':
            doc = knowledge.get_document(parse_qs(url.query).get('id', [''])[0])
            return self.send_json(200 if doc else 404, doc or {'error': '文档不存在'})
        if self.path == '/api/status':
            return self.send_json(200, {'ready': config.is_ready(), 'model': config.MODEL, 'max_turns': config.MAX_TURNS})
        if self.path not in ('/', '/index.html'):
            return self.send_json(404, {'error': '页面不存在'})
        data = Path(__file__).with_name('workbench.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path not in ('/api/chat', '/api/knowledge', '/api/knowledge/delete', '/api/knowledge/search', '/api/extensions/skill', '/api/extensions/toggle', '/api/extensions/delete'):
            return self.send_json(404, {'error': '接口不存在'})
        # Only accept browser requests from this local workbench.
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:7861', 'http://localhost:7861'):
            return self.send_json(403, {'error': '请求来源不受支持'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 262144:
                return self.send_json(413, {'error': '请求过大或为空'})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求格式错误')
            if self.path == '/api/extensions/skill':
                return self.send_json(200, extensions.save_skill(body))
            if self.path == '/api/extensions/toggle':
                return self.send_json(200, extensions.toggle(body.get('kind'), body.get('id'), body.get('enabled')))
            if self.path == '/api/extensions/delete':
                return self.send_json(200, extensions.delete_skill(body.get('id')))
            if self.path == '/api/knowledge':
                return self.send_json(201, knowledge.add_document(body.get('name'), body.get('content')))
            if self.path == '/api/knowledge/delete':
                doc_id = body.get('id')
                if not isinstance(doc_id, str):
                    raise ValueError('文档 ID 格式错误')
                removed = knowledge.delete_document(doc_id)
                return self.send_json(200 if removed else 404, {'deleted': removed})
            if self.path == '/api/knowledge/search':
                query = body.get('query')
                if not isinstance(query, str) or not query.strip() or len(query) > 16000:
                    raise ValueError('请输入检索内容')
                return self.send_json(200, {'sources': knowledge.search(query)})
            active = extensions.resolve(body.get('skill_id'))
            question = body.get('question', '')
            history = body.get('history', [])
            if not isinstance(question, str) or not question.strip() or len(question) > 16000:
                raise ValueError('请输入 1–16000 字的问题')
            if not isinstance(history, list) or any(not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str) for m in history):
                raise ValueError('会话记录格式错误')
        except (ValueError, TypeError, AttributeError) as exc:
            return self.send_json(400, {'error': str(exc) or '请求格式错误'})
        if not config.is_ready():
            return self.send_json(503, {'error': '尚未连接模型。请在 .env 配置 QA_LLM_BASE_URL、QA_LLM_API_KEY 和 QA_LLM_MODEL，然后重启服务。'})
        mem = memory.ConversationMemory(max_turns=config.MAX_TURNS)
        for message in history[-config.MAX_TURNS * 2:]:
            mem.add(message['role'], message['content'])
        try:
            import qa
            sources = knowledge.search(question) if body.get('use_knowledge', False) and active['knowledge'] else []
            answer = (qa.ask_with_tools if body.get('use_tools', True) else qa.ask)(mem, question.strip(), context=knowledge.context(sources), skill_prompt=active['prompt'], tool_names=active['tool_names'])
            if not answer:
                return self.send_json(502, {'error': '模型未返回答案，工具调用可能已达到步数上限，请重试。'})
            self.send_json(200, {'answer': answer, 'sources': sources, 'knowledge_used': bool(sources)})
        except Exception:
            self.send_json(502, {'error': '模型请求失败，请检查服务端模型配置、网络及额度后重试。'})


if __name__ == '__main__':
    print('AI 工作台：http://127.0.0.1:7861', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 7861), Handler).serve_forever()
