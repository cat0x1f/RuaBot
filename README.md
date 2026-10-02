# RuaBot

使用时需要关闭隐私模式。

感谢：

- [GooGuJiang/Gugumoe-bot](https://github.com/GooGuJiang/Gugumoe-bot/)
- [rikumi/tietie-bot](https://github.com/rikumi/tietie-bot/)
- [sxyazi/bendan](https://github.com/sxyazi/bendan/)

## 环境变量

```bash
export BOT_TOKEN=7816288053:AAGGmCm17YsPTHSYM5WOoHcV9akHOW0xyEM
export ALLOWED_GROUPS=-1001852815669,-1268145665910
export LOG_LEVEL=INFO
export BSKY_HANDLE=alice.bsky.social
export BSKY_POLL_INTERVAL=60
export BSKY_STATE_FILE=/app/data/bsky_state.json
```

配置了 `BSKY_HANDLE` 后，机器人会轮询该 Bluesky 用户的最新帖子，并自动转发到 `ALLOWED_GROUPS` 里的群组/频道。

说明：

- `BSKY_HANDLE`：要跟踪的 Bluesky 用户 handle，例如 `alice.bsky.social`
- `BSKY_POLL_INTERVAL`：轮询间隔，单位秒，默认 `60`
- `BSKY_STATE_FILE`：已转发帖子的去重状态文件路径，默认 `/app/data/bsky_state.json`
- Bluesky 文本帖会直接发送帖子正文
- 如果帖子带图片，会连同图片一起转发；不会额外附带作者名、标题或链接
- 回复、转帖不会转发
- 只接受纯文本帖或文本加图片帖；如果包含引用、外链卡片、视频等非图片内容，会整条跳过

