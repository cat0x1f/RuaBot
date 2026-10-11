# RuaBot

使用时需要关闭隐私模式。

感谢以下的项目：

- [GooGuJiang/Gugumoe-bot](https://github.com/GooGuJiang/Gugumoe-bot/)
- [rikumi/tietie-bot](https://github.com/rikumi/tietie-bot/)
- [sxyazi/bendan](https://github.com/sxyazi/bendan/)

感谢以下的 AI 工具：

- 吃白饭的大肥鱼和他的朋友们
- OpenCode

## 环境变量

```bash
# Telegram Bot 配置
export BOT_TOKEN=7816288053:AAGGmCm17YsPTHSYM5WOoHcV9akHOW0xyEM
export ALLOWED_GROUPS=-1001852815669,-1268145665910
export LOG_LEVEL=INFO

# 日志配置
export LOG_FILE=/app/data/ruabot.log
export LOG_MAX_BYTES=10485760
export LOG_BACKUP_COUNT=5

# Bluesky → Telegram 转发（默认关闭）
export ENABLE_BSKY_TO_TG=true
export BSKY_HANDLE=alice.bsky.social
export BSKY_POLL_INTERVAL=60
export BSKY_STATE_FILE=/app/data/bsky_state.json

# Twitter → Bluesky → Telegram 转发（默认关闭）
export ENABLE_TWITTER_TO_BSKY=true
export TWITTER_HANDLE=your_twitter_handle
export BSKY_POST_HANDLE=your.bsky.social
export BSKY_POST_PASSWORD=xxxx-xxxx-xxxx-xxxx
export TWITTER_POLL_INTERVAL=60
export TWITTER_STATE_FILE=/app/data/twitter_state.json
```

### 日志配置

- `LOG_FILE`：日志文件路径，默认 `/app/data/ruabot.log`，留空则只输出到控制台
- `LOG_MAX_BYTES`：单个日志文件最大大小（字节），默认 `10485760`（10MB）
- `LOG_BACKUP_COUNT`：保留的日志文件数量，默认 `5`

日志轮转：当日志文件达到最大大小时，会自动创建新文件，旧文件重命名为 `ruabot.log.1`、`ruabot.log.2` 等，最多保留指定数量的备份。

## 功能说明

### Bluesky → Telegram 转发

配置了 `ENABLE_BSKY_TO_TG=true` 和 `BSKY_HANDLE` 后，机器人会轮询该 Bluesky 用户的最新帖子，并自动转发到 `ALLOWED_GROUPS` 里的群组/频道。

说明：

- `ENABLE_BSKY_TO_TG`：开关，设置为 `true` 启用，默认 `false`
- `BSKY_HANDLE`：要跟踪的 Bluesky 用户 handle，例如 `alice.bsky.social`
- `BSKY_POLL_INTERVAL`：轮询间隔，单位秒，默认 `60`
- `BSKY_STATE_FILE`：已转发帖子的去重状态文件路径，默认 `/app/data/bsky_state.json`
- Bluesky 文本帖会直接发送帖子正文
- 如果帖子带图片，会连同图片一起转发；不会额外附带作者名、标题或链接
- 回复、转帖不会转发
- 只接受纯文本帖或文本加图片帖；如果包含引用、外链卡片、视频等非图片内容，会整条跳过

### Twitter → Bluesky → Telegram 转发

配置了 `ENABLE_TWITTER_TO_BSKY=true` 和相关参数后，机器人会：
1. 轮询指定 Twitter 账号的最新推文
2. 将符合条件的推文转发到 Bluesky
3. 同时转发到 `ALLOWED_GROUPS` 里的群组/频道

说明：

- `ENABLE_TWITTER_TO_BSKY`：开关，设置为 `true` 启用，默认 `false`
- `TWITTER_HANDLE`：要跟踪的 Twitter 用户名（不带 @），例如 `elonmusk`
- `BSKY_POST_HANDLE`：用于发帖的 Bluesky 账号 handle
- `BSKY_POST_PASSWORD`：Bluesky App Password（在 Settings → Privacy and security → App passwords 生成）
- `TWITTER_POLL_INTERVAL`：轮询间隔，单位秒，默认 `60`
- `TWITTER_STATE_FILE`：已转发推文的去重状态文件路径，默认 `/app/data/twitter_state.json`

转发规则：

- 转发纯文本推文、文本+图片推文（最多4张）
- 跳过回复、引用推文、包含视频/GIF、包含外链卡片
- 跳过文本超过 300 字符的推文（Bluesky 限制）
- 只转发主推，不转发推文线程中的其他推文

