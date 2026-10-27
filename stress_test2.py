# 第二轮压测: 匿名链路 8 场景
import concurrent.futures, time, json, statistics, urllib.request, urllib.error, sys
BASE='http://127.0.0.1:8916'
def post(p, body, timeout=200):
    t0=time.time()
    req=urllib.request.Request(BASE+p, method='POST', data=json.dumps(body).encode())
    req.add_header('Content-Type','application/json')
    try:
        r=urllib.request.urlopen(req, timeout=timeout)
        return r.status, r.read().decode(), round((time.time()-t0)*1000)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), round((time.time()-t0)*1000)
    except Exception as e:
        return 0, str(e)[:120], round((time.time()-t0)*1000)
def get(p, timeout=15):
    try:
        r=urllib.request.urlopen(BASE+p, timeout=timeout)
        return r.status, r.read().decode(), 0
    except Exception as e:
        return 0, str(e)[:120], 0
results=[]
def rec(name, ok, detail):
    results.append(ok); print(('PASS' if ok else 'FAIL'), name, '|', detail)

rs=[get('/health') for _ in range(20)]
rec('health x20', all(r[0]==200 for r in rs), '20/20')

s,d,_=post('/v1/images/generations', {})
rec('edge empty 400', s==400, f'{s}')
s,d,_=post('/v1/unknown', {})
rec('edge 404', s==404, f'{s}')

s,d,_=post('/native/playMethods', {})
try: j=json.loads(d); ok=s==200 and j.get('code')=='00000'
except: ok=False
rec('native playMethods(100模板)', ok, f'{s}')

# 串行生图 x2
ts=[]; allok=True
for i in range(2):
    s,d,ms=post('/v1/images/generations', {'prompt':f'a {["red","blue"][i]} balloon'}, timeout=200)
    try: j=json.loads(d); ok=s==200 and any(u.get('url') for u in j.get('data',[]))
    except: ok=False
    allok=allok and ok; ts.append(ms)
    print('   gen',i,s,ms,'ms')
rec('serial gen x2', allok, f'{ts} ms')

# 并发 x5 (安全线内)
t0=time.time()
with concurrent.futures.ThreadPoolExecutor(5) as ex:
    futs=[ex.submit(post,'/v1/images/generations',{'prompt':'a cute cat'}, 200) for _ in range(5)]
    rs=[f.result() for f in futs]
ok=sum(1 for s,_,_ in rs if s==200)
det=0
for s,d,_ in rs:
    try:
        j=json.loads(d); det+=sum(1 for u in j.get('data',[]) if u.get('url'))
    except: pass
rec('concurrent x5 gen', ok>=4, f'{ok}/5 http200, {det} urls, wall {round(time.time()-t0)}s')

npass=sum(results)
print(f'\n=== {npass}/{len(results)} PASS ===')
sys.exit(0 if npass==len(results) else 1)
