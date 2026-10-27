import io, json, sys, tempfile, types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import knowledge as k
import extensions
with tempfile.TemporaryDirectory() as d:
 k.DB_PATH=Path(d)/'kb.sqlite3'
 extensions.DB_PATH=Path(d)/'extensions.sqlite3'
 a=k.add_document('产品路线.md','星河工作台采用本地优先设计。季度目标是支持知识库检索和文档引用。')
 b=k.add_document('travel.txt','The Kyoto itinerary includes gardens and temples.')
 assert len(k.list_documents())==2
 assert k.search('知识库检索')[0]['id']==a['id']
 assert k.search('Kyoto')[0]['id']==b['id']
 assert not k.search('zxqvnomatch')
 assert k.get_document(a['id'])['content'].startswith('星河')
 try:k.add_document('empty','   ');raise AssertionError()
 except ValueError:pass
 import config, memory
 seen=[]
 sys.modules['llm']=types.SimpleNamespace(chat=lambda messages:seen.append(messages) or '根据资料 [来源 1]')
 import qa
 mem=memory.ConversationMemory()
 ctx=k.context(k.search('知识库检索'))
 assert '[来源 1]' in qa.ask(mem,'项目目标是什么',context=ctx)
 assert ctx in seen[0][1]['content']
 assert mem.to_messages()[0]['content']=='项目目标是什么'
 import workbench as w
 class Fake:
  send_json=w.Handler.send_json
  def __init__(self,path,payload):
   self.path=path;data=json.dumps(payload).encode();self.headers={'Content-Length':str(len(data))};self.rfile=io.BytesIO(data);self.wfile=io.BytesIO();self.status=None
  def send_response(self,s):self.status=s
  def send_header(self,*args):pass
  def end_headers(self):pass
 config.is_ready=lambda:True
 h=Fake('/api/chat',{'question':'知识库检索','use_knowledge':True,'use_tools':False});w.Handler.do_POST(h)
 result=json.loads(h.wfile.getvalue());assert h.status==200 and result['sources'] and result['knowledge_used']
 h=Fake('/api/chat',{'question':'知识库检索','use_knowledge':False,'use_tools':False});w.Handler.do_POST(h)
 assert json.loads(h.wfile.getvalue())['sources']==[]
 assert k.delete_document(a['id']) and not k.get_document(a['id'])
 assert not k.search('知识库检索')
print('PASS: persistence, Chinese/English search, empty results, validation, retrieval context, citations metadata, opt-out, deletion')
