# 完全手工 raw socket: 精确控制每个头顺序, 模拟 okhttp 发包
import socket, ssl, hashlib, base64, subprocess, json, time, hmac, sys, random
sys.path.insert(0,'.')
from urllib.parse import quote

PUB = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3bahNR2MaPTf3vCNwORGKjMb+QtvnE58W6PlnXnm8lxYxkpRq4NtcotZm8x5DPnTbfCwrZ0YLh1uOmOCTY+ECYliWT2C6PI0fD8ryleh5+PNmYZVfNq2IVxGIJ+TQ5N2SnpmFgg2TFUg//Cu93GO+0GHJ2B5xzXqi8direBQjZwIDAQAB"
pem = "-----BEGIN PUBLIC KEY-----\n" + '\n'.join(PUB[i:i+64] for i in range(0,len(PUB),64)) + "\n-----END PUBLIC KEY-----"
open('_pub.pem','w').write(pem)
def gen_key():
    chars=[chr(c) for c in range(30,40)]+[chr(c) for c in range(65,91)]+[chr(c) for c in range(97,123)]
    out=[]
    for _ in range(16):
        i=random.randint(0,len(chars)-1)
        out.append(str(i) if i<10 else chars[i])
    return ''.join(out)
def body_args(o):
    vals=[]
    def walk(o):
        if o is None: return
        if isinstance(o,list):
            for v in o: walk(v)
        elif isinstance(o,dict):
            for k in sorted(o.keys()): walk(o[k])
        elif isinstance(o,bool): vals.append('true' if o else 'false')
        else: vals.append(str(o))
    walk(o); return vals

device_id='8c6cbf9371916bce'
device_key='htY8W9j0tz4PomSUW7ZHQU+I36JbSbFA76IEGM/hUJc='
ts=str(int(time.time()*1000)); key=gen_key()
r=subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey','_pub.pem','-pkeyopt','rsa_padding_mode:pkcs1'],input=key.encode(),capture_output=True)
ak_b64=base64.b64encode(r.stdout).decode()
akey_md5=hashlib.md5(ak_b64.encode()).hexdigest().lower()
ut=hmac.new(device_key.encode(), key.encode(), hashlib.sha256).hexdigest()
body={"appId":"","prompt":"hi","sessionId":""}
enc=quote(''.join(body_args(body))+ts, safe='')
rr=subprocess.run(['openssl','enc','-aes-128-ecb','-K',key.encode().hex(),'-nosalt'],input=enc.encode(),capture_output=True)
sign_val=hashlib.md5(base64.b64encode(rr.stdout).decode().encode()).hexdigest().lower()
# okhttp 头顺序: 程序头(自定义)在前, Host/UA/其他由 okhttp 放后(实际 okhttp: Host, Connection, Accept-Encoding, UA, 自定义头...)
# okhttp 4.x 真实顺序: [Host, Connection, Accept-Encoding, User-Agent, ...自定义...]
H = [
 ('Host','ai-api.buscari.com'),
 ('Connection','Keep-Alive'),
 ('Accept-Encoding','identity'),
 ('User-Agent','okhttp/4.12.0'),
 ('clientType','android_buscari'),
 ('versionCode','211'),
 ('buildCode','154'),
 ('platformId','4'),
 ('channel','android_buscari'),
 ('appName','seekee'),
 ('deviceId',device_id),
 ('mobileId',device_id),
 ('sysVer','11'),
 ('model','sdk_gphone64_x86_64'),
 ('deviceModel','sdk_gphone64_x86_64'),
 ('system','11'),
 ('appLanguage','en'),
 ('lang','en'),
 ('netType','1'),
 ('netStatus','1'),
 ('emulator','0'),
 ('keke','0'),
 ('areacode','unknown'),
 ('timezone','GMT+08:00'),
 ('zone','GMT+08:00'),
 ('package','com.enzo.paulo'),
 ('adId',''),
 ('usertype',ut),
 ('curTime',ts),
 ('signVal',sign_val),
 ('aKey',akey_md5),
 ('app_request_aes_key',key),
 ('Accept','text/event-stream'),
 ('Content-Type','application/json; charset=utf-8'),
 ('Content-Length',str(len(json.dumps(body)))),
]
data=json.dumps(body).encode()
req=f"POST /quan/ai/aegis/stream/doChat HTTP/1.1\r\n"+''.join(f'{k}: {v}\r\n' for k,v in H)+"\r\n"+data.decode()
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
ss=ctx.wrap_socket(socket.create_connection(('ai-api.buscari.com',443),timeout=30),server_hostname='ai-api.buscari.com')
ss.sendall(req.encode())
buf=b''; t0=time.time()
try:
    while time.time()-t0<45:
        c=ss.recv(4096)
        if not c: break
        buf+=c
        if len(buf)>6000: break
except: pass
ss.close()
bp = buf.split(b'\r\n\r\n',1)[1] if b'\r\n\r\n' in buf else buf
import re
print(re.sub(rb'[0-9a-f]{1,4}\r\n',b'',bp)[:800].decode('utf-8','ignore'))
