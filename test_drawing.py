"""绘图协议与本地文件测试；模拟服务，不调用或计费真实模型。"""
import base64
import io
import json
import tempfile
from pathlib import Path
import drawing
import extensions
import config

with tempfile.TemporaryDirectory() as directory:
    drawing.ASSET_DIR = Path(directory) / 'images'
    extensions.DB_PATH = Path(directory) / 'extensions.sqlite3'
    config.IMAGE_BASE_URL = 'https://images.example/v1'
    config.IMAGE_API_KEY = 'test-only'
    config.IMAGE_MODEL = 'test-image-model'
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVJkAAAAASUVORK5CYII=')
    calls = []
    def fake_open(request, timeout):
        calls.append(json.loads(request.data))
        assert request.full_url == 'https://images.example/v1/images/generations'
        return io.BytesIO(json.dumps({'data': [{'b64_json': base64.b64encode(png).decode()}]}).encode())
    drawing.urlopen = fake_open
    result = drawing.generate('测试画面', '1536x1024', 'watercolor')
    assert calls[0]['n'] == 1 and calls[0]['size'] == '1536x1024' and '水彩' in calls[0]['prompt']
    file, mime = drawing.get_image(result['id'])
    assert file.read_bytes() == png and mime == 'image/png'
    assert drawing.get_image('../../.env') is None
    try:
        drawing.validate('', '1024x1024', 'natural')
        raise AssertionError('empty prompt accepted')
    except ValueError:
        pass
    def bad_open(request, timeout):
        return io.BytesIO(b'{"data":[{"url":"https://example.com/image.png"}]}')
    drawing.urlopen = bad_open
    try:
        drawing.generate('test')
        raise AssertionError('unsupported URL result accepted')
    except ValueError:
        pass
    import workbench
    class Fake:
        send_json = workbench.Handler.send_json
        def __init__(self):
            self.path = '/api/drawing/generate'
            data = json.dumps({'prompt': 'test'}).encode()
            self.headers = {'Content-Length': str(len(data))}
            self.rfile = io.BytesIO(data)
            self.wfile = io.BytesIO()
        def send_response(self, status): self.status = status
        def send_header(self, *args): pass
        def end_headers(self): pass
    extensions.toggle('plugin', 'drawing', False)
    h = Fake(); workbench.Handler.do_POST(h)
    assert h.status == 403
    extensions.toggle('plugin', 'drawing', True)
    config.IMAGE_MODEL = ''
    h = Fake(); workbench.Handler.do_POST(h)
    assert h.status == 503
print('PASS: generation payload, styles, local image storage, path validation, invalid prompt, unsupported output, plugin disabled, missing configuration')
