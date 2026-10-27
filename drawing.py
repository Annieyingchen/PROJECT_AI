"""服务端图片生成；使用 /images/generations，要求返回 b64_json。"""
import base64
import binascii
import json
import re
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

import config

ASSET_DIR = Path(__file__).with_name('drawing_assets')
LOCK = threading.Lock()
SIZES = {'1024x1024', '1536x1024', '1024x1536'}
STYLES = {'natural': '', 'illustration': '插画风格，清晰的视觉层次，协调的配色。', 'photo': '摄影风格，自然光线，真实材质。', 'watercolor': '水彩风格，柔和笔触，纸张质感。', 'minimal': '极简设计，简洁几何，克制配色，充足留白。'}


def status():
    return {'ready': bool(config.IMAGE_BASE_URL and config.IMAGE_API_KEY and config.IMAGE_MODEL), 'model': config.IMAGE_MODEL}


def validate(prompt, size, style):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        raise ValueError('画面描述需为 1–4000 字')
    if size not in SIZES or style not in STYLES:
        raise ValueError('绘图尺寸或风格不受支持')


def generate(prompt, size='1024x1024', style='natural'):
    validate(prompt, size, style)
    if not status()['ready']:
        raise ValueError('请先在 .env 配置 QA_IMAGE_BASE_URL、QA_IMAGE_API_KEY 和 QA_IMAGE_MODEL，然后重启服务')
    full_prompt = prompt.strip() + ('\n' + STYLES[style] if STYLES[style] else '')
    payload = {'model': config.IMAGE_MODEL, 'prompt': full_prompt, 'size': size, 'n': 1}
    request = Request(config.IMAGE_BASE_URL.rstrip('/') + '/images/generations', data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + config.IMAGE_API_KEY, 'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=180) as response:
        data = response.read(40_000_001)
    if len(data) > 40_000_000:
        raise ValueError('模型返回图片过大')
    try:
        encoded = json.loads(data)['data'][0]['b64_json']
        raw = base64.b64decode(encoded, validate=True)
    except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
        raise ValueError('接口未返回有效的 b64_json 图片，请检查绘图接口兼容性') from None
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        extension, mime = 'png', 'image/png'
    elif raw.startswith(b'\xff\xd8\xff'):
        extension, mime = 'jpg', 'image/jpeg'
    elif raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        extension, mime = 'webp', 'image/webp'
    else:
        raise ValueError('接口返回的图片格式不是 PNG、JPEG 或 WebP')
    ASSET_DIR.mkdir(exist_ok=True)
    image_id = uuid4().hex
    filename = image_id + '.' + extension
    (ASSET_DIR / filename).write_bytes(raw)
    item = {'id': image_id, 'filename': filename, 'mime': mime, 'prompt': prompt.strip(), 'size': size, 'style': style, 'model': config.IMAGE_MODEL}
    (ASSET_DIR / (image_id + '.json')).write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
    return {**item, 'url': '/api/drawing/file?id=' + image_id}


def get_image(image_id):
    if not isinstance(image_id, str) or not re.fullmatch('[0-9a-f]{32}', image_id):
        return None
    meta = ASSET_DIR / (image_id + '.json')
    if not meta.exists():
        return None
    item = json.loads(meta.read_text(encoding='utf-8'))
    if item['filename'] not in [image_id + '.' + ext for ext in ('png', 'jpg', 'webp')]:
        return None
    return ASSET_DIR / item['filename'], item['mime']
