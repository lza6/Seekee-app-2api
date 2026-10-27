# Seekee-app-2api
---

## 第三轮：动态分析定案（2026-10-28）

### 模拟器路线成果

爱加密壳 x86_64 适配版（`signed4/seekee_x86_shell-aligned-debugSigned.apk`）成功运行进入主界面。关键技术：

1. **壳 x86 适配**：壳代码走 `System.loadLibrary("exec_x86")` — 从 `assets/ijm_lib/x86_64/` 复制 `libexec.so → libexec_x86.so` 塞进 `lib/x86_64/`，删除 `lib/arm64-v8a` 强制 x86_64 安装
2. **壳存活规律**：仅「卸载→安装→第一次启动」有数分钟存活窗口，之后每次冷启动壳静默自毁（无 FATAL/无 crash log）。Frida attach 必须抢此窗口
3. **设备凭据提取**：`su 0 cat /data/data/com.enzo.paulo/shared_prefs/global.xml` → `sp_localDeviceId` / `sp_localDeviceKey`

### DEVICEID_SIGN 风控定案（决定性实验）

用 raw socket 按 okhttp 精确头序 + **真实 deviceKey/deviceId + 正确 usertype HMAC** 重放 doChat：

```
usertype = HMAC-SHA256(b64(AES-ECB(deviceId, RSA_PUB[:16])), app_request_aes_key)  ← 算法 100% 验证一致
→ 仍返回 DEVICEID_SIGN_1000128
```

**结论**：服务器校验的是 deviceId 的**服务器侧注册状态**（绑定首启会话），与签名/头序/TLS 指纹无关，离线不可绕过。

### mitm 路线受阻

模拟器代理 10.0.2.2:8888 可见全部 SNI（buscari 三域名确认）；tmpfs 挂载 system CA 成功，但壳 okhttp 内嵌 certificate pinner → `Client TLS handshake failed`。mitm 需先过壳的 pinner（frida 绕过），或直接真机。

### 最终能力边界

| 能力 | 状态 |
|---|---|
| t2i 生图（匿名） | ✅ 全链路，demo :8916 可用 |
| OSS 上传 | ✅ |
| 玩法模板/配置 | ✅ |
| i2i / doChat / speech | ⛔ 服务器侧设备注册风控，需真机 frida 抓首启注册序列后重放 |

### 复现实验工具

- `raw_replay2.py` — okhttp 头序 raw socket 重放（决定性实验）
- `replay_h2.js` — Node HTTP/2 重放
- `cacerts_new/c8750f0d.0` — 标准 Android 格式 mitm CA
