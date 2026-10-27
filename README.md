# Seekee v2.13.1 逆向与 2API Demo

> **📦 new-api 渠道对接请看 [docs/NEW-API-INTEGRATION.md](docs/NEW-API-INTEGRATION.md)** — 含完整签名协议、Go 实现要点、联调清单，对接会话照做即可。

> 目标 APK: `Seekee v2.13.1 b211 (Premium by @ElaMods).apk`（包名 `com.enzo.paulo`，React Native + 原生混合架构）
>
> **状态: 三轮协议还原完成。t2i 匿名生图全链路可用，无需登录。**

## 能力总览

| 能力 | 端点 | 状态 |
|---|---|---|
| 文生图 t2i | `POST /quan/tools/ai/center/textToImage` + `GET getTaskResult` | ✅ 全链路打通，出图 8-20s |
| 玩法模板 100 个 | `POST /quan/tools/ai/v2/template/play-methods-list` | ✅ |
| 出图比例 | `GET /quan/tools/ai/v2/template/image-ratio` | ✅ 5 种（1024/1365/1820） |
| 图片上传 OSS | `GET /quan/tools/oss/tokenv2` + 阿里 OSS V4 PostObject | ✅ 上传成功 |
| 限速 | t2i | ✅ 无 IP/设备硬限速；高并发偶发 `-100003` 挤兑，重试即恢复 |
| 图生图 i2i | `POST /quan/tools/ai/v2/image/generate/submit` | ⛔ 服务器侧设备注册风控（第三轮定案） |
| AI Chat SSE | `POST ai-api/quan/ai/aegis/stream/doChat` | ⛔ 同上（`DEVICEID_SIGN_1000128`） |
| speech ASR | `wss://speech-api.buscari.com` | ⛔ 同风控 + 壳 certificate pinner |

## 上游架构

```
App (com.enzo.paulo, RN+原生混合, 爱加密壳)
 ├─ mobile-api.buscari.com   ← 业务网关(Spring) 全部 /quan/ /buscari/ 端点 【主力】
 ├─ ai-api.buscari.com       ← AI SSE (doChat/doPhotoHandler)
 ├─ cloud-api.buscari.com    ← 云盘 (Spring, /health UP)
 ├─ speech-api.buscari.com   ← ASR WebSocket (wss, root upgrade)
 ├─ h5-api.buscari.com       ← H5 内嵌页 API
 └─ bgc-us-east.oss-accelerate.aliyuncs.com ← 阿里 OSS (图片中转)
生图上游: 阿里通义 dashscope (bucket dashscope-5859.oss-cn-wulanchabu-acdr-1)
```

## 鉴权协议（完整还原，已实测）

### 请求头（HeaderInterceptor / AIHeaderInterceptor）

```
固定头: clientType=android_buscari  versionCode=211  buildCode=154(!!)  platformId=4
        channel=android_buscari  appName=seekee  package=com.enzo.paulo
        deviceId/mobileId(自生成16hex)  sysVer  model  deviceModel  system
        appLanguage=en  lang=en  zone/timezone  netType  netStatus
        emulator=0  keke=0  areacode  adId  usertype
签名头: curTime(毫秒)  signVal  aKey  app_request_aes_key
```

> **⚠️ buildCode 必须 =154**（ApiVersionCode 而非真实 build 211），传 211 得 `-50006`。

### 签名算法（EncryptAesUtil）

1. 参数值序列化：POST = JSON 值按 key 字典序递归拼接（bool→true/false，跳过 null）；GET = query 值按 URL 顺序拼接，**值需 URL-decode**
2. `raw = concat(values) + curTime`
3. `enc = urlencode_strict(raw)`
4. 每请求 16 位随机 aesKey（0-9 A-Z a-z + chr(30..39)，index<10 输出数字本身）
5. `aKey = base64(RSA/ECB/PKCS1(aesKey))` — 公钥硬编码 APK
6. `app_request_aes_key = md5(aKey)` 小写
7. `signVal = md5(base64(AES/ECB/PKCS5(enc, aesKey)))` 小写

> **⚠️ 头语义反直觉**：`aKey` 头收 RSA 块，`app_request_aes_key` 头收 md5。

**响应解密**：`code=00000` 且 data 为长 base64 时，`data = AES-ECB(json, 请求侧aesKey)`。

**错误码**：`00000` 成功 / `-10001` param（风控会伪装） / `-10002` sign错 / `-10000` 系统错 / `-100003` 挤兑(重试恢复) / `-10003` 未登录 / `-50006` buildCode不合法 / `-50008` 上游错。

### 设备签名风控（第三轮定案）

```
deviceKey = base64(AES-ECB(deviceId, key=RSA_PUB_b64[:16]))
usertype  = HMAC-SHA256(deviceKey, app_request_aes_key头值) hex
```
算法 100% 验证一致，但 raw socket + 真实 deviceKey 重放仍被拒 → **服务器校验 deviceId 的服务器侧注册状态**（绑定首启会话），离线不可绕过。t2i 等匿名端点不校验此层。

## 交付物

- `full_client.py` — 协议客户端（签名/加密/解密/OSS 上传全实现，**唯一权威实现**）
- `demo_server.py` — 端口 8916：OpenAI 兼容 `POST /v1/images/generations`（同步出图 + `-100003` 挤兑重试）+ `/native/*` 透传 + `/health` `/stats`
- `demo.html` — 中文 demo 页 → http://127.0.0.1:8916/
- `stress_test2.py` — 压测 6 场景 **6/6 PASS**：health x20 median 1ms / 边界 400·404 / 透传 3.9s / 串行生图 8.9-16.7s / 并发 x5 全成功（wall 39s）
- `raw_replay2.py` / `replay_h2.js` — 决定性实验重放工具
- `docs/PROTOCOL.md` — 协议细节速查 + jadx 混淆映射表
- `docs/NEW-API-INTEGRATION.md` — **new-api 对接指南**
- `docs/sample_output.png` / `cat_result.png` — 实测出图样本

## 快速开始

```bash
# 零第三方依赖: 标准库 + openssl CLI
python demo_server.py            # :8916
curl -X POST http://127.0.0.1:8916/v1/images/generations \
  -H 'Content-Type: application/json' -d '{"prompt":"a cute cat in space"}'
```

## 第三轮动态定案（摘要）

爱加密壳 x86_64 适配版可运行进主界面；壳仅「卸载→安装→首启」存活数分钟窗口；deviceKey 算法 100% 验证一致但服务器仍拒 → **服务器侧 deviceId 注册状态校验**，离线不可绕过；壳 okhttp 内嵌 certificate pinner，模拟器 mitm 无效。详见 git 历史 `dc6d6b1`。

## 后续方向

i2i / doChat / speech 解锁需真机 + Frida 抓首启注册序列（重放完整初始化）。
