// Node http2 重放 doChat — okhttp 用 HTTP/2, python 用 HTTP/1.1 可能就是差异!
const http2 = require('http2');
const crypto = require('crypto');
const { execSync } = require('child_process');
const fs = require('fs');

const PUB = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3bahNR2MaPTf3vCNwORGKjMb+QtvnE58W6PlnXnm8lxYxkpRq4NtcotZm8x5DPnTbfCwrZ0YLh1uOmOCTY+ECYliWT2C6PI0fD8ryleh5+PNmYZVfNq2IVxGIJ+TQ5N2SnpmFgg2TFUg//Cu93GO+0GHJ2B5xzXqi8direBQjZwIDAQAB";
fs.writeFileSync('_pub.pem', "-----BEGIN PUBLIC KEY-----\n" + PUB.replace(/(.{64})/g, "$1\n") + "\n-----END PUBLIC KEY-----");

function genKey() {
  const chars = [];
  for (let i = 30; i < 40; i++) chars.push(String.fromCharCode(i));
  for (let i = 65; i < 91; i++) chars.push(String.fromCharCode(i));
  for (let i = 97; i < 123; i++) chars.push(String.fromCharCode(i));
  let out = '';
  for (let i = 0; i < 16; i++) {
    const idx = Math.floor(Math.random() * chars.length);
    out += idx < 10 ? String(idx) : chars[idx];
  }
  return out;
}
function bodyArgs(obj) {
  const vals = [];
  function walk(o) {
    if (o === null || o === undefined) return;
    if (Array.isArray(o)) { o.forEach(walk); return; }
    if (typeof o === 'object') { Object.keys(o).sort().forEach(k => walk(o[k])); return; }
    if (typeof o === 'boolean') { vals.push(o ? 'true' : 'false'); return; }
    vals.push(String(o));
  }
  walk(obj);
  return vals;
}
const device_id = process.argv[2] || '8c6cbf9371916bce';
const device_key = process.argv[3] || 'htY8W9j0tz4PomSUW7ZHQU+I36JbSbFA76IEGM/hUJc=';
const body = { appId: '', prompt: 'hello, who are you? one sentence', sessionId: '' };
const ts = String(Date.now());
const key = genKey();
const ak = execSync(`openssl pkeyutl -encrypt -pubin -inkey _pub.pem -pkeyopt rsa_padding_mode:pkcs1`, { input: key }).toString('base64');
const akey_md5 = crypto.createHash('md5').update(ak).digest('hex');
const usertype = crypto.createHmac('sha256', device_key).update(key).digest('hex');
const raw = bodyArgs(body).join('') + ts;
const enc = encodeURIComponent(raw).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
const enc2 = enc.replace(/%20/g, '%20');
const sb = execSync(`openssl enc -aes-128-ecb -K ${Buffer.from(key).toString('hex')} -nosalt`, { input: enc2 });
const signVal = crypto.createHash('md5').update(sb.toString('base64')).digest('hex');

const client = http2.connect('https://ai-api.buscari.com');
client.on('error', e => { console.error('h2err', e.message); process.exit(1); });
const req = client.request({
  ':method': 'POST', ':path': '/quan/ai/aegis/stream/doChat',
  'clientType': 'android_buscari', 'versionCode': '211', 'buildCode': '154',
  'platformId': '4', 'channel': 'android_buscari', 'appName': 'seekee',
  'deviceId': device_id, 'mobileId': device_id, 'sysVer': '11',
  'model': 'sdk_gphone64_x86_64', 'deviceModel': 'sdk_gphone64_x86_64', 'system': '11',
  'appLanguage': 'en', 'lang': 'en', 'netType': '1', 'netStatus': '1',
  'emulator': '0', 'keke': '0', 'areacode': 'unknown', 'timezone': 'GMT+08:00',
  'zone': 'GMT+08:00', 'package': 'com.enzo.paulo', 'adId': '', 'usertype': usertype,
  'curTime': ts, 'signVal': signVal, 'aKey': akey_md5, 'app_request_aes_key': key,
  'accept': 'text/event-stream', 'content-type': 'application/json; charset=utf-8',
  'user-agent': 'okhttp/4.12.0'
});
req.on('error', e => console.error('stream err:', e.message));
req.write(JSON.stringify(body));
let buf = '';
req.on('data', c => buf += c);
req.on('end', () => { console.log(buf.substring(0, 1200)); client.close(); });
setTimeout(() => { console.log('TIMEOUT', buf.substring(0, 300)); process.exit(0); }, 30000);
