# 更新日志

## 新增功能：Twitter → Bluesky → Telegram 转发

### 功能概述

新增从 Twitter 自动转发到 Bluesky 和 Telegram 的功能，与现有的 Bluesky → Telegram 转发并行运行。

### 主要特性

1. **双向转发系统**
   - Bluesky → Telegram（原有功能，现在可通过开关控制）
   - Twitter → Bluesky → Telegram（新功能）

2. **智能过滤**
   - ✅ 只转发纯文本或文本+图片的推文
   - ❌ 自动跳过：回复、引用、视频、GIF、外链
   - ❌ 跳过超过 300 字符的推文（Bluesky 限制）

3. **开关控制**
   - `ENABLE_BSKY_TO_TG`：控制 Bluesky → Telegram
   - `ENABLE_TWITTER_TO_BSKY`：控制 Twitter → Bluesky → Telegram
   - 默认都是关闭状态，需要显式启用

4. **状态持久化**
   - 防止重复转发
   - 支持断点续传
   - 独立的状态文件管理

### 配置示例

```bash
# 启用 Twitter → Bluesky → Telegram 转发
export ENABLE_TWITTER_TO_BSKY=true
export TWITTER_HANDLE=your_twitter_handle
export BSKY_POST_HANDLE=your.bsky.social
export BSKY_POST_PASSWORD=xxxx-xxxx-xxxx-xxxx

# 启用 Bluesky → Telegram 转发（可选）
export ENABLE_BSKY_TO_TG=true
export BSKY_HANDLE=alice.bsky.social
```

### 技术实现

- **API 使用**：FxTwitter API（无需 Twitter API key）
- **Bluesky 集成**：atproto Python SDK
- **图片处理**：自动上传到 Bluesky（最多 4 张）
- **错误处理**：完善的限流和重试机制

### 依赖更新

新增依赖：
- `atproto`：Bluesky AT Protocol SDK

### 文件变更

- ✨ `commands/twitter_to_bsky.py`：新增 Twitter 转发模块
- 📝 `main.py`：集成双向转发功能
- 📝 `requirements.txt`：添加 atproto 依赖
- 📝 `README.md`：更新文档
- ✨ `.env.example`：配置示例文件

### 使用说明

1. 获取 Bluesky App Password：
   - 登录 Bluesky
   - 进入 Settings → Privacy and security → App passwords
   - 创建新的 app password
   - 复制 password（格式：xxxx-xxxx-xxxx-xxxx）

2. 设置环境变量（见 `.env.example`）

3. 启动机器人

### 注意事项

- Bluesky 文本限制 300 字符
- 图片最多 4 张，每张不超过 1MB
- 建议轮询间隔至少 60 秒，避免被限流
- Twitter handle 不需要 @ 前缀

### 日志示例

```
2024-01-01 12:00:00 - INFO: Starting Twitter→Bluesky→Telegram poller for elonmusk → alice.bsky.social → ['-1001852815669']
2024-01-01 12:00:01 - INFO: Successfully logged in to Bluesky as alice.bsky.social
2024-01-01 12:00:05 - INFO: Initialized twitter poller for elonmusk at 10 tweets
2024-01-01 12:01:00 - INFO: Posted to Bluesky: at://did:plc:xxx/app.bsky.feed.post/yyy
2024-01-01 12:01:01 - INFO: Forwarded tweet 1234567890 to Bluesky: at://did:plc:xxx/app.bsky.feed.post/yyy
2024-01-01 12:01:02 - INFO: Forwarded tweet 1234567890 to Telegram: ['-1001852815669']
```
