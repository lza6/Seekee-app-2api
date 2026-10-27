# Seekee 协议完整客户端(签名+加密+解密) — 已验证可用
import urllib.request, ssl, time, hashlib, base64, subprocess, random, json
from urllib.parse import quote
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
PUB = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3bahNR2MaPTf3vCNwORGKjMb+QtvnE58W6PlnXnm8lxYxkpRq4NtcotZm8x5DPnTbfCwrZ0YLh1uOmOCTY+ECYliWT2C6PI0fD8ryleh5+PNmYZVfNq2IVxGIJ+TQ5N2SnpmFgg2TFUg//Cu93GO+0GHJ2B5xzXqi8direBQjZwIDAQAB"
_PEM = "-----BEGIN PUBLIC KEY-----\n" + '\n'.join(PUB[i:i+64] for i in range(0,len(PUB),64)) + "\n-----END PUBLIC KEY-----"
open('_pub.pem','w').write(_PEM)

def gen_key():
    chars=[chr(c) for c in range(30,40)]+[chr(c) for c in range(65,91)]+[chr(c) for c in range(97,123)]
    out=[]
    for _ in range(16):
        i=random.randint(0,len(chars)-1)
        out.append(str(i) if i<10 else chars[i])
    return ''.join(out)

def body_args(obj):
    vals=[]
    def walk(o):
        if isinstance(o,dict):
            for k in sorted(o.keys()): walk(o[k])
        elif isinstance(o,list):
            for v in o: walk(v)
        elif isinstance(o,bool): vals.append('true' if o else 'false')
        elif o is not None: vals.append(str(o))
    walk(obj)
    return vals

def aes_dec(data_b64, key):
    raw = base64.b64decode(data_b64)
    r = subprocess.run(['openssl','enc','-d','-aes-128-ecb','-K',key.encode().hex(),'-nosalt'],input=raw,capture_output=True)
    return r.stdout.decode('utf-8','ignore')

class Seekee:
    def __init__(self, device_id=None, token=None):
        self.device = device_id or ''.join(random.choice('0123456789abcdef') for _ in range(16))
        self.token = token
    def req(self, path, method='GET', body=None, base='https://mobile-api.buscari.com', query='', raw=False):
        ts = str(int(time.time()*1000))
        key = gen_key()
        r = subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey','_pub.pem','-pkeyopt','rsa_padding_mode:pkcs1'],input=key.encode(),capture_output=True)
        ak_b64 = base64.b64encode(r.stdout).decode()
        akey_md5 = hashlib.md5(ak_b64.encode()).hexdigest().lower()
        if method=='GET' and query:
            from urllib.parse import unquote
            args=[unquote(kv.split('=',1)[1]) if '=' in kv else kv for kv in query.split('&')]
        elif body: args = body_args(body)
        else: args = []
        raw_str = ''.join(args)+ts
        enc = quote(raw_str, safe='')
        rr = subprocess.run(['openssl','enc','-aes-128-ecb','-K',key.encode().hex(),'-nosalt'],input=enc.encode(),capture_output=True)
        sb64 = base64.b64encode(rr.stdout).decode()
        sign_val = hashlib.md5(sb64.encode()).hexdigest().lower()
        url = base+path+(('?'+query) if query else '')
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, method=method, data=data)
        H={'User-Agent':'okhttp/4.12.0','Content-Type':'application/json',
           'clientType':'android_buscari','versionCode':'211','buildCode':'154',
           'platformId':'4','channel':'android_buscari','appName':'seekee',
           'deviceId':self.device,'mobileId':self.device,
           'sysVer':'14','model':'Pixel 8','deviceModel':'Pixel 8','system':'14',
           'appLanguage':'en','lang':'en','netType':'1','netStatus':'1',
           'emulator':'0','keke':'0','areacode':'unknown',
           'timezone':'GMT+08:00','zone':'GMT+08:00',
           'package':'com.enzo.paulo','adId':'','usertype':'1',
           'curTime':ts,'signVal':sign_val,'aKey':ak_b64,'app_request_aes_key':akey_md5}
        if self.token: H['token']=self.token
        for k,v in H.items(): request.add_header(k,v)
        try:
            resp = urllib.request.urlopen(request, timeout=20, context=ctx)
            code = resp.status; txt = resp.read().decode('utf-8','ignore')
        except urllib.error.HTTPError as e:
            return e.code, {'raw': e.read().decode('utf-8','ignore')}
        try:
            j = json.loads(txt)
            if j.get('code')=='00000' and isinstance(j.get('data'),str) and len(j['data'])>40 and not raw:
                try: j['data'] = json.loads(aes_dec(j['data'], key))
                except Exception: j['data'] = aes_dec(j['data'], key)
            return code, j
        except Exception:
            return code, {'raw': txt}
