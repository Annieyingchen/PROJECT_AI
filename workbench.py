"""AI 工作台：python workbench.py；复用现有问答和记忆层。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import config
import memory


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
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
        if self.path != '/api/chat':
            return self.send_json(404, {'error': '接口不存在'})
        # Only accept browser requests from this local workbench.
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:7861', 'http://localhost:7861'):
            return self.send_json(403, {'error': '请求来源不受支持'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 262144:
                return self.send_json(413, {'error': '请求过大或为空'})
            body = json.loads(self.rfile.read(length))
            question = body.get('question', '')
            history = body.get('history', [])
            if not isinstance(question, str) or not question.strip() or len(question) > 16000:
                raise ValueError('请输入 1–16000 字的问题')
            if not isinstance(history, list) or any(not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str) for m in history):
                raise ValueError('会话记录格式错误')
        except (ValueError, TypeError, AttributeError):
            return self.send_json(400, {'error': '请求格式错误，请检查问题和会话记录'})
        if not config.is_ready():
            return self.send_json(503, {'error': '尚未连接模型。请在 .env 配置 QA_LLM_BASE_URL、QA_LLM_API_KEY 和 QA_LLM_MODEL，然后重启服务。'})
        mem = memory.ConversationMemory(max_turns=config.MAX_TURNS)
        for message in history[-config.MAX_TURNS * 2:]:
            mem.add(message['role'], message['content'])
        try:
            import qa
            answer = (qa.ask_with_tools if body.get('use_tools', True) else qa.ask)(mem, question.strip())
            if not answer:
                return self.send_json(502, {'error': '模型未返回答案，工具调用可能已达到步数上限，请重试。'})
            self.send_json(200, {'answer': answer})
        except Exception:
            self.send_json(502, {'error': '模型请求失败，请检查服务端模型配置、网络及额度后重试。'})


if __name__ == '__main__':
    print('AI 工作台：http://127.0.0.1:7861', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 7861), Handler).serve_forever()
