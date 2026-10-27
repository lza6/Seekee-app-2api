# Seekee 协议细节速查

## 签名实现参考 (Python)

```python
# 1. 生成 16 位随机 aesKey
chars = [chr(c) for c in range(30,40)] + list(upper) + list(lower)
# kotlin 逻辑: i<10 输出数字本身, 否则输出字符
for _ in range(16):
    i = rand(0, len(chars)-1)
    out.append(str(i) if i < 10 else chars[i])

# 2. RSA 加密 aesKey (公钥硬编码)
ak_b64 = b64(RSA_PKCS1(aesKey))          # → aKey 头
app_request_aes_key = md5(ak_b64)         # → app_request_aes_key 头

# 3. signVal
raw = concat(body_values_sorted_by_key) + curTime_ms   # POST
# GET: raw = concat([unquote(v) for v in query_values_in_url_order]) + curTime
enc = urlencode_strict(raw)
signVal = md5(b64(AES_ECB_PKCS5(enc, aesKey))).lower()

# 4. 响应解密: code=00000 且 data 长 b64 → AES_ECB decrypt with aesKey
```

## OpenSSL 命令行等价

```bash
# RSA 加密
openssl pkeyutl -encrypt -pubin -inkey pub.pem -pkeyopt rsa_padding_mode:pkcs1
# AES-ECB
openssl enc -aes-128-ecb -K $(echo -n key | xxd -p) -nosalt
```

## 设备签名 (风控层, 部分端点)

```
deviceKey = b64(AES_ECB(deviceId, key=RSA_PUB_b64[:16]))   # RSA_PUB_b64 前16字符 'MIGfMA0GCSqGSIb3'
usertype  = hex(HMAC_SHA256(deviceKey, app_request_aes_key头值))
```

## 混淆映射 (jadx)

| 混淆名 | 原名 |
|---|---|
| `p328o0OO0o0o.o00O0O` | UrlConfig.kt |
| `p328o0OO0o0o.Oooo0` | 环境常量 (channel/versionCode) |
| `com.enzo.library_base.net.o000oOoO` | HeadInterceptor.kt |
| `com.enzo.library_base.net.OooO00o` | AIHeaderInterceptor.kt |
| `com.enzo.library_base.net.AppInterceptor` | AppInterceptor.kt (签名+解密) |
| `com.enzo.library_network.util.EncryptAesUtil` | EncryptAesUtil.kt |
| `com.enzo.library_network.util.DeviceIdManager` | DeviceIdManager.kt |
| `p284o0O0Oo0.OooOOO0` | AI v2 接口 (generate/collection) |
| `p284o0O0Oo0.OooOOOO` | 业务接口大全 (user/oss/config) |
| `p379o0OOooOO.o000000O` | AIConfig.kt (SSE 端点) |
| `p287o0O0OoO.o00O0O0` | OSS 上传 (uploadImageToOss) |
| `o00oO0o` = @POST, `OooOo` = @GET, `OooOO0O` = @Body, `o0O0O00` = @QueryMap, `oo0o0Oo` = @Query |
