import time
import os
import threading
import telebot
import logging
import commands.jrrp
import commands.handle
import commands.bsky
import commands.twitter_to_bsky

BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "/app/data/ruabot.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 默认 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))  # 默认保留 5 个
ALLOWED_GROUPS = set(os.getenv("ALLOWED_GROUPS", "-1145141919810").split(","))

# Bluesky → Telegram 配置
BSKY_HANDLE = os.getenv("BSKY_HANDLE", "").strip()
ENABLE_BSKY_TO_TG = os.getenv("ENABLE_BSKY_TO_TG", "false").lower() in ("true", "1", "yes", "on")

# Twitter → Bluesky → Telegram 配置
TWITTER_HANDLE = os.getenv("TWITTER_HANDLE", "").strip()
BSKY_POST_HANDLE = os.getenv("BSKY_POST_HANDLE", "").strip()
BSKY_POST_PASSWORD = os.getenv("BSKY_POST_PASSWORD", "").strip()
ENABLE_TWITTER_TO_BSKY = os.getenv("ENABLE_TWITTER_TO_BSKY", "false").lower() in ("true", "1", "yes", "on")


def parse_poll_interval(env_var: str, default: int = 60) -> int:
    try:
        return max(10, int(os.getenv(env_var, str(default))))
    except ValueError:
        logging.getLogger().warning(
            "Invalid %s, fallback to %d seconds", env_var, default
        )
        return default


BSKY_POLL_INTERVAL = parse_poll_interval("BSKY_POLL_INTERVAL", 60)
TWITTER_POLL_INTERVAL = parse_poll_interval("TWITTER_POLL_INTERVAL", 60)

MAX_AI_CHAT_MESSAGE_LENGTH = 100

log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
level = log_levels.get(LOG_LEVEL, logging.INFO)

# 配置日志格式
log_format = "%(asctime)s - %(levelname)s: %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# 创建日志目录
if LOG_FILE:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

# 配置日志处理器
handlers = []

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(log_format, date_format))
handlers.append(console_handler)

# 文件处理器（带轮转）
if LOG_FILE:
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    handlers.append(file_handler)

# 配置根日志记录器
logging.basicConfig(
    level=level,
    handlers=handlers
)
logger = logging.getLogger()

if not BOT_TOKEN:
    logger.error("No BOT_TOKEN")
    exit(1)

if LOG_FILE:
    logger.info("Logs will be saved to: %s", LOG_FILE)

bot = telebot.TeleBot(token=BOT_TOKEN, parse_mode="HTML")


def is_allowed_group(chat_id: int) -> bool:
    return str(chat_id) in ALLOWED_GROUPS or "-1145141919810" in ALLOWED_GROUPS


def get_bsky_target_chats() -> list[str]:
    return sorted(
        [
            chat_id.strip()
            for chat_id in ALLOWED_GROUPS
            if chat_id.strip() and chat_id.strip() != "-1145141919810"
        ]
    )


@bot.message_handler(commands=["jrrp"])
def command_jrrp(message) -> None:
    if is_allowed_group(message.chat.id):
        bot.reply_to(message, commands.jrrp.main(message.from_user.id))


@bot.message_handler(func=lambda message: True)
def handle_text_message(message) -> None:
    if is_allowed_group(message.chat.id):
        logger.debug(f"JUST TEXT HANDLE - {message}")
        if response := commands.handle.main(message):
            bot.reply_to(message, response)


def start_bot():
    target_chats = get_bsky_target_chats()

    # 启动 Bluesky → Telegram 轮询器
    if ENABLE_BSKY_TO_TG and BSKY_HANDLE and target_chats:
        logger.info(
            "Starting Bluesky→Telegram poller for %s → %s",
            BSKY_HANDLE,
            target_chats,
        )
        threading.Thread(
            target=commands.bsky.poll_latest_posts,
            args=(bot, BSKY_HANDLE, target_chats, BSKY_POLL_INTERVAL),
            daemon=True,
        ).start()
    elif ENABLE_BSKY_TO_TG and BSKY_HANDLE:
        logger.warning(
            "Bluesky→Telegram poller is disabled because no valid ALLOWED_GROUPS target is configured"
        )
    elif BSKY_HANDLE:
        logger.info("Bluesky→Telegram poller is disabled by ENABLE_BSKY_TO_TG=false")

    # 启动 Twitter → Bluesky 轮询器
    if ENABLE_TWITTER_TO_BSKY and TWITTER_HANDLE and BSKY_POST_HANDLE and BSKY_POST_PASSWORD:
        logger.info(
            "Starting Twitter→Bluesky poller for %s → %s",
            TWITTER_HANDLE,
            BSKY_POST_HANDLE,
        )
        threading.Thread(
            target=commands.twitter_to_bsky.poll_and_post,
            args=(
                TWITTER_HANDLE,
                BSKY_POST_HANDLE,
                BSKY_POST_PASSWORD,
                TWITTER_POLL_INTERVAL,
            ),
            daemon=True,
        ).start()
    elif ENABLE_TWITTER_TO_BSKY:
        logger.warning(
            "Twitter→Bluesky poller is disabled: missing configuration (TWITTER_HANDLE, BSKY_POST_HANDLE, or BSKY_POST_PASSWORD)"
        )
    elif TWITTER_HANDLE:
        logger.info("Twitter→Bluesky poller is disabled by ENABLE_TWITTER_TO_BSKY=false")

    while True:
        try:
            logger.info("I'm Running!")
            bot.polling(non_stop=True)
        except Exception as e:
            logger.error(f"Connection error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    start_bot()
