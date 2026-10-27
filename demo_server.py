# Seekee 2API demo server - OpenAI 兼容 + 原生端点 (端口 8916)
# 协议来源: Seekee v2.13.1 逆向 (签名/加密/解密已还原)
import json, time, threading, queue, random, hashlib, base64, subprocess, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlparse, parse_qs
import urllib.request, ssl

import full_client as fc  # 复用 Seekee 协议客户端

SEEK = {}
_stats = {'req':0,'err':0,'tasks':0}
_lock = threading.Lock()
_tasks = {}  # taskId -> {status,url,...}

def get_client(key='default'):
    with _lock:
        if key not in SEEK:
            SEEK[key] = fc.Seekee()
        return SEEK[key]

class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(b)))
        self.send_header('Connection','close')
        self.end_headers()
        self.wfile.write(b)
        self.close_connection = True

    def do_GET(self):
        _stats['req'] += 1
        p = urlparse(self.path).path
        if p == '/health':
            return self._json(200, {'status':'ok','clients':len(SEEK),'stats':_stats})
        if p == '/stats':
            return self._json(200, _stats)
        if p == '/' or p == '/demo.html':
            b = open('demo.html','rb').read()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(b)))
            self.send_header('Connection','close')
            self.end_headers()
            self.wfile.write(b); self.close_connection=True
            return
        return self._json(404, {'error':'not found'})

    def do_POST(self):
        _stats['req'] += 1
        p = urlparse(self.path).path
        try: body = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
        except Exception: body = {}
        try:
            if p == '/v1/images/generations':
                # OpenAI 兼容生图
                prompt = body.get('prompt','')
                if not prompt: 
                    _stats['err'] += 1
                    return self._json(400, {'error':{'message':'prompt required','type':'invalid_request_error'}})
                c = get_client()
                j = None
                for _attempt in range(3):
                    code, j = c.req('/quan/tools/ai/center/textToImage','POST',{'question':prompt,'appId':''})
                    if j.get('code') == '00000': break
                    if str(j.get('code')) == '-100003':
                        time.sleep(2)
                        c = get_client('retry'+str(random.random()))
                        continue
                    break
                if j.get('code') != '00000':
                    _stats['err'] += 1
                    return self._json(502, {'error':{'message':str(j.get('msg')),'type':'upstream_error','code':str(j.get('code'))}})
                tid = j['data']['taskId']
                _stats['tasks'] += 1
                for _ in range(90):
                    time.sleep(2)
                    try:
                        code2, j2 = c.req('/quan/tools/ai/center/getTaskResult','GET',None,query=f'taskId={tid}')
                    except Exception:
                        continue
                    if isinstance(j2.get('raw'),str) and 'sign' in j2['raw']:
                        c2 = get_client('retry'+str(random.random()))
                        code2, j2 = c2.req('/quan/tools/ai/center/getTaskResult','GET',None,query=f'taskId={tid}')
                    if j2.get('code')=='00000':
                        st = j2['data'].get('taskStatus')
                        if st == 'SUCCEEDED':
                            urls = [r['url'] for r in j2['data'].get('results',[])]
                            return self._json(200, {'created':int(time.time()),'data':[{'url':u} for u in urls]})
                        if st not in ('PENDING','RUNNING','PROCESSING','SUBMITTED','QUEUED'):
                            _stats['err'] += 1
                            return self._json(502, {'error':{'message':'task '+str(st),'type':'upstream_error'}})
                _stats['err'] += 1
                return self._json(504, {'error':{'message':'timeout','type':'upstream_error'}})
            elif p == '/native/textToImage':
                c = get_client()
                code, j = c.req('/quan/tools/ai/center/textToImage','POST',body)
                return self._json(200, j)
            elif p == '/native/getTaskResult':
                c = get_client()
                code, j = c.req('/quan/tools/ai/center/getTaskResult','GET',None,query=f"taskId={body.get('taskId','')}")
                return self._json(200, j)
            elif p == '/native/playMethods':
                c = get_client()
                code, j = c.req('/quan/tools/ai/v2/template/play-methods-list','POST',body or {})
                return self._json(200, j)
            else:
                return self._json(404, {'error':'not found'})
        except Exception as e:
            _stats['err'] += 1
            return self._json(500, {'error':{'message':str(e)[:200],'type':'internal'}})

PORT = 8916
if __name__ == '__main__':
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), H)
    print(f'Seekee demo server on :{PORT}')
    srv.serve_forever()
