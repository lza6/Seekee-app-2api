# Seekee t2i → new-api 渠道对接指南

> 给对接会话的完整说明。上游协议已全部还原并实测闭环，照本指南实现一个自定义渠道类型即可。

## 一、对接方案总览

| 项 | 值 |
|---|---|
| 能力范围 | **仅 t2i 文生图**（OpenAI `/v1/images/generations` 兼容） |
| 建议渠道类型 | 新增自定义 type（参考 AIVM type72 先例），或用「OpenAI 兼容图像」自定渠道 |
| 上游 | `mobile-api.buscari.com`（Spring 网关）→ 阿里 dashscope 出图 |
| 鉴权 | **匿名可用**，无需账号/密钥。签名协议自包含（RSA+AES 每请求生成） |
| 出图耗时 | 8-20s（提交 → PENDING → 轮询 → SUCCEEDED） |
| 限速 | 无 IP/设备硬限速；高并发（>5）挤兑触发 `-100003`，**重试即恢复**。建议渠道并发 ≤5 + `-100003` 自动重试 |
| 参考实现 | 本仓库 `full_client.py`（协议客户端）+ `demo_server.py`（OpenAI 兼容层），逐行可移植 |

## 二、上游调用流程（3 个请求完成一次生图）

```
① POST https://mobile-api.buscari.com/quan/tools/ai/center/textToImage
   body: {"question": "<用户prompt>", "appId": ""}
   → {"code":"00000","data":{"taskId":"...","taskStatus":"PENDING"}}

② (循环, 每 2.5s) GET https://mobile-api.buscari.com/quan/tools/ai/center/getTaskResult?taskId=<id>
   → {"code":"00000","data":{"taskStatus":"SUCCEEDED","results":[{"url":"https://dashscope-...oss...png"}]}}
   taskStatus 流转: PENDING → (RUNNING) → SUCCEEDED | FAILED
   超时上限建议 90s

③ 返回 results[].url（阿里 OSS 签名 URL，有效期长，可直接透传给用户或转存）
```

**遇到 `-100003`（挤兑）→ sleep 2s 换一个设备指纹重试，最多 3 次。**

## 三、签名协议（必须完整实现，缺一即 `-10002`）

### 3.1 请求头（每个请求都要带）

```
# 固定头（照抄）
clientType: android_buscari
versionCode: 211
buildCode: 154            ⚠️ 必须是 154（=ApiVersionCode），传真实 build 211 会 -50006
platformId: 4
channel: android_buscari
appName: seekee
package: com.enzo.paulo
deviceId: <16位hex，服务启动时随机生成一次并固定>
mobileId: <同 deviceId>
sysVer: 14
model: Pixel 8
deviceModel: Pixel 8
system: 14
appLanguage: en
lang: en
netType: 1
netStatus: 1
emulator: 0
keke: 0
areacode: unknown
timezone: GMT+08:00
zone: GMT+08:00
adId: 
usertype: <见 3.4，可为空串（t2i 不校验）>

# 签名头（每请求新生成）
curTime: <毫秒时间戳>
aKey: <b64(RSA-PKCS1(aesKey))>          ← 注意：服务器拿它解密
app_request_aes_key: <md5(aKey)>        ← 注意：是其 md5，别按名字猜
signVal: <md5(b64(AES-ECB(urlencode(参数值拼接+curTime))))>  小写
```

### 3.2 signVal 计算

1. **参数值序列化**：
   - POST：JSON body 所有值按 key 字典序拼接（递归进数组/对象；bool→`true/false`；跳过 null）
   - GET：URL query 的**值**按 URL 出现顺序拼接，**每个值先 URL-decode**
2. `raw = 拼接结果 + curTime毫秒`
3. `enc = strict_urlencode(raw)`（标准 percent-encoding 即可，Python `quote(raw, safe='')`）
4. 每请求生成 16 位随机 aesKey：字符集 = `0-9` + `A-Z` + `a-z`（生成时随机 index<10 输出数字字符本身，否则输出字符——照抄 `full_client.py:gen_key()`）
5. `signVal = md5( base64( AES-128-ECB-PKCS5( enc, aesKey ) ) ).lower()`

### 3.3 aKey / app_request_aes_key

- RSA 公钥（硬编码于 APK，直接用）：
```
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3bahNR2MaPTf3vCNwORGKjMb+QtvnE58W6PlnXnm8lxYxkpRq4NtcotZm8x5DPnTbfCwrZ0YLh1uOmOCTY+ECYliWT2C6PI0fD8ryleh5+PNmYZVfNq2IVxGIJ+TQ5N2SnpmFgg2TFUg//Cu93GO+0GHJ2B5xzXqi8direBQjZwIDAQAB
```
- `aKey = base64( RSA/ECB/PKCS1Padding( aesKey, 公钥 ) )`
- `app_request_aes_key = md5(aKey).hex().lower()`
- ⚠️ **头语义反直觉**：`aKey` 传 RSA 块（服务器私钥解出 aesKey 解密 signVal），`app_request_aes_key` 传 md5

### 3.4 usertype（t2i 可空）

`usertype = HMAC-SHA256( deviceKey, app_request_aes_key头值 ).hex()`
其中 `deviceKey = base64( AES-128-ECB( deviceId, key=RSA公钥b64字符串前16字符 ) )`。
t2i 端点不校验此头，**传空串即可**；若实现 i2i/doChat（需真机注册的 deviceId）才需要。

### 3.5 响应解密

响应 `code=00000` 且 `data` 为长 base64 字符串时：
`data = AES-128-ECB-PKCS5-decrypt( base64decode(data), 请求侧 aesKey )` → JSON。

### 3.6 错误码

| code | 处理 |
|---|---|
| `00000` | 成功 |
| `-100003` | 并发挤兑 → 换 deviceId 重试（≤3次） |
| `-10002` | 签名错 → 检查 3.2/3.3 实现 |
| `-50006` | buildCode 错 → 必须 154 |
| `-10001` | param error（在 textToImage 上通常=body 格式错） |

## 四、Go 实现要点（对接 new-api 的 relay/channel/seekee/）

1. **AES-ECB**：Go 标准库无 ECB，自写 ECB 分块 + `cipher.NewECBEncrypter`（参考项目内已有 ECB 实现，若无可抄 crypto.go 常见实现 ~20 行）
2. **RSA-PKCS1**：`crypto/rsa EncryptPKCS1v15`，公钥用 `x509.ParsePKIXPublicKey(base64解码)` — 公钥正好是标准 SPKI 格式
3. **每请求新 aesKey**：不要复用，服务器可能关联校验
4. **deviceId**：渠道初始化时 `hex.EncodeToString(randomBytes(8))` 固定；建议每渠道实例独立（或设备池轮换分散风控）
5. **轮询**：`relay` 内同步轮询（2.5s 间隔，90s 上限），new-api 对 t2i 是同步接口，直接阻塞到出 URL
6. **超时**：HTTP 客户端 30s/请求，整任务 120s
7. **计费**：按次计费（QuotaPerRequest），模型名建议 `seekee-t2i`（512/768/1024 尺寸上游自动定，不透传 w/h —— textToImage 端点不收尺寸参数，出图比例由上游默认）

## 五、联调自测清单（对接完成后逐项跑）

```bash
# 1. 协议客户端独立验证（先跑这个，通了再写 Go）
python full_client.py  # 或参照 probe 脚本直接调 textToImage
# 期望: code 00000 + taskId

# 2. demo 全链路验证
python demo_server.py  # :8916
curl -X POST http://127.0.0.1:8916/v1/images/generations \
  -H 'Content-Type: application/json' -d '{"prompt":"a red apple"}'
# 期望: 200 + data[0].url 可下载

# 3. Go 渠道单测（httptest 假上游）+ 真实上游各一轮
# 4. new-api 渠道创建 → /v1/images/generations 代理 → 出图
```

## 六、风险与备注

- 上游是免费 App 网关，随时可能加风控（doChat/i2i 已加 DEVICEID_SIGN）。t2i 目前未加，但建议渠道做好 `-10002` 频发的熔断告警
- 出图 URL 是阿里 OSS 带签名 URL（有效期长但非永久），new-api 透传即可；若要永久存储需转存自有 OSS
- 勿高并发打上游（保持 ≤5），避免把这条免费通道打挂
- 本仓库 `full_client.py` 是唯一权威协议实现，Go 移植时逐函数对照；协议细节疑问看 `docs/PROTOCOL.md`
