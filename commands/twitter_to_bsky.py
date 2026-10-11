import html
import json
import logging
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from atproto import Client

FXTWITTER_BASE_URL = "https://api.fxtwitter.com"
TWITTER_STATUSES_ENDPOINT = "/2/profile/{handle}/statuses"
STATE_FILE = os.getenv("TWITTER_STATE_FILE", "/app/data/twitter_state.json")
MAX_SEEN_IDS = 200
MAX_TEXT_LENGTH = 300  # Bluesky 限制

logger = logging.getLogger(__name__)


class TwitterRateLimitError(RuntimeError):
    pass


class BskyClient:
    def __init__(self, handle: str, password: str):
        self.client = Client()
        try:
            self.client.login(handle, password)
            logger.info("Successfully logged in to Bluesky as %s", handle)
        except Exception as exc:
            logger.error("Failed to login to Bluesky: %s", exc)
            raise

    def post(self, text: str, image_urls: list[str] = None) -> str:
        """发布帖子到 Bluesky，返回帖子 URI"""
        try:
            if image_urls:
                # 下载图片数据
                images_data = []
                for url in image_urls[:4]:  # Bluesky 最多 4 张图片
                    try:
                        img_data = self._download_image(url)
                        images_data.append(img_data)
                        logger.debug("Downloaded image: %s", url)
                    except Exception as exc:
                        logger.warning("Failed to download image %s: %s", url, exc)

                if images_data:
                    # 发帖带图片
                    response = self.client.send_images(text=text, images=images_data)
                else:
                    # 图片全部失败，只发文本
                    response = self.client.send_post(text=text)
            else:
                # 纯文本
                response = self.client.send_post(text=text)

            uri = response.uri
            logger.info("Posted to Bluesky: %s", uri)
            return uri
        except Exception as exc:
            logger.error("Failed to post to Bluesky: %s", exc)
            raise

    def _download_image(self, url: str) -> bytes:
        """下载图片"""
        req = Request(url, headers={"User-Agent": "RuaBot/1.0"})
        with urlopen(req, timeout=30) as response:
            return response.read()


def load_seen_ids() -> list[str] | None:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as state_file:
            data = json.load(state_file)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load twitter state from %s: %s", STATE_FILE, exc)
        return None

    if not isinstance(data, list):
        logger.warning("Invalid twitter state in %s, starting fresh", STATE_FILE)
        return None

    return [tweet_id for tweet_id in data if isinstance(tweet_id, str)]


def save_seen_ids(seen_ids: list[str]) -> None:
    directory = os.path.dirname(STATE_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_file = f"{STATE_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as state_file:
            json.dump(seen_ids[-MAX_SEEN_IDS:], state_file)
        os.replace(temp_file, STATE_FILE)
    except OSError as exc:
        logger.error("Failed to save twitter state to %s: %s", STATE_FILE, exc)


def poll_and_post(
    twitter_handle: str,
    bsky_handle: str,
    bsky_password: str,
    interval_seconds: int,
) -> None:
    """轮询 Twitter 并转发到 Bluesky"""
    # 初始化 Bluesky 客户端
    try:
        bsky_client = BskyClient(bsky_handle, bsky_password)
    except Exception as exc:
        logger.error("Failed to initialize Bluesky client: %s", exc)
        return

    # 加载已处理的推文 ID
    loaded_ids = load_seen_ids()
    initialized = loaded_ids is not None
    seen_ids = loaded_ids or []
    seen_set = set(seen_ids)

    if initialized:
        logger.info("Loaded %d seen tweets from %s", len(seen_ids), STATE_FILE)

    def remember(tweet_id: str) -> None:
        if tweet_id in seen_set:
            return
        seen_set.add(tweet_id)
        seen_ids.append(tweet_id)
        if len(seen_ids) > MAX_SEEN_IDS:
            seen_set.discard(seen_ids.pop(0))

    while True:
        try:
            tweets = fetch_latest_tweets(twitter_handle)
            if not tweets:
                logger.debug("No tweets found for twitter handle %s", twitter_handle)
            elif not initialized:
                # 首次运行，只记录不转发
                for tweet in tweets:
                    remember(tweet["id"])
                save_seen_ids(seen_ids)
                initialized = True
                logger.info(
                    "Initialized twitter poller for %s at %d tweets",
                    twitter_handle,
                    len(seen_ids),
                )
            else:
                # 处理新推文（按时间顺序）
                for tweet in reversed(tweets):
                    tweet_id = tweet["id"]
                    if tweet_id in seen_set:
                        continue

                    remember(tweet_id)
                    save_seen_ids(seen_ids)

                    try:
                        # 转发到 Bluesky
                        bsky_uri = bsky_client.post(
                            text=tweet["text"], image_urls=tweet.get("images", [])
                        )
                        logger.info("Forwarded tweet %s to Bluesky: %s", tweet_id, bsky_uri)
                    except Exception as exc:
                        logger.error("Failed to forward tweet %s: %s", tweet_id, exc)
        except TwitterRateLimitError as exc:
            logger.warning("Twitter rate limited for %s: %s", twitter_handle, exc)
        except Exception as exc:
            logger.error("Twitter polling failed for %s: %s", twitter_handle, exc)

        time.sleep(interval_seconds)


def fetch_latest_tweets(handle: str, limit: int = 10) -> list[dict[str, Any]]:
    """获取最新推文，只返回符合条件的推文"""
    url = f"{FXTWITTER_BASE_URL}{TWITTER_STATUSES_ENDPOINT.format(handle=handle)}?count={limit}"
    logger.debug("Fetching tweets from: %s", url)
    response_data = fetch_json(url)

    tweets = []
    for item in response_data.get("results", []):
        if item.get("type") != "status":
            continue

        # 提取推文基本信息
        tweet_id = extract_tweet_id(item.get("url", ""))
        if not tweet_id:
            continue

        text = html.unescape((item.get("text") or "").strip())

        # 检查文本长度
        if len(text) > MAX_TEXT_LENGTH:
            logger.info("Skipped tweet %s: text too long (%d > %d)", tweet_id, len(text), MAX_TEXT_LENGTH)
            continue

        # 检查是否为回复
        if item.get("replying_to"):
            logger.info("Skipped tweet %s: is a reply", tweet_id)
            continue

        # 检查媒体类型
        media = item.get("media") or {}
        images = []
        has_unsupported_media = False

        # 检查是否有不支持的内容
        if item.get("quote"):
            logger.info("Skipped tweet %s: contains quote", tweet_id)
            continue

        if media.get("videos"):
            logger.info("Skipped tweet %s: contains video", tweet_id)
            continue

        if media.get("external"):
            logger.info("Skipped tweet %s: contains external link", tweet_id)
            continue

        # 提取图片
        photos = media.get("photos", [])
        if photos:
            images = [photo.get("url") for photo in photos if photo.get("url")]

        # 只接受纯文本或文本+图片
        if not text and not images:
            logger.info("Skipped tweet %s: empty content", tweet_id)
            continue

        tweets.append(
            {
                "id": tweet_id,
                "text": text,
                "images": images,
                "url": item.get("url", ""),
            }
        )

    return tweets


def fetch_json(url: str) -> dict[str, Any]:
    """调用 API 获取 JSON 数据"""
    try:
        req = Request(url, headers={"User-Agent": "RuaBot/1.0"})
        with urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise TwitterRateLimitError("HTTP 429 from Twitter API") from exc
        raise RuntimeError(f"HTTP {exc.code} from Twitter API") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling Twitter API: {exc.reason}") from exc


def extract_tweet_id(url: str) -> str | None:
    """从 URL 中提取推文 ID"""
    if not url:
        return None
    parts = url.rstrip("/").split("/")
    if len(parts) > 0 and parts[-1].isdigit():
        return parts[-1]
    return None
