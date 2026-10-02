import html
import json
import logging
import os
import time
from typing import Any
from telebot import types
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

APPVIEW_BASE_URL = "https://public.api.bsky.app"
AUTHOR_FEED_ENDPOINT = "/xrpc/app.bsky.feed.getAuthorFeed"
STATE_FILE = os.getenv("BSKY_STATE_FILE", "/app/data/bsky_state.json")
MAX_SEEN_URIS = 200

logger = logging.getLogger(__name__)


class BskyRateLimitError(RuntimeError):
    pass


def load_seen_uris() -> list[str] | None:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as state_file:
            data = json.load(state_file)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load bsky state from %s: %s", STATE_FILE, exc)
        return None

    if not isinstance(data, list):
        logger.warning("Invalid bsky state in %s, starting fresh", STATE_FILE)
        return None

    return [uri for uri in data if isinstance(uri, str)]


def save_seen_uris(seen_uris: list[str]) -> None:
    directory = os.path.dirname(STATE_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_file = f"{STATE_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as state_file:
            json.dump(seen_uris[-MAX_SEEN_URIS:], state_file)
        os.replace(temp_file, STATE_FILE)
    except OSError as exc:
        logger.error("Failed to save bsky state to %s: %s", STATE_FILE, exc)


def poll_latest_posts(
    bot,
    handle: str,
    chat_ids: list[str],
    interval_seconds: int,
) -> None:
    loaded_uris = load_seen_uris()
    initialized = loaded_uris is not None
    seen_uris = loaded_uris or []
    seen_set = set(seen_uris)

    if initialized:
        logger.info("Loaded %d seen bsky posts from %s", len(seen_uris), STATE_FILE)

    def remember(uri: str) -> None:
        if uri in seen_set:
            return
        seen_set.add(uri)
        seen_uris.append(uri)
        if len(seen_uris) > MAX_SEEN_URIS:
            seen_set.discard(seen_uris.pop(0))

    while True:
        try:
            posts = fetch_latest_posts(handle)
            if not posts:
                logger.debug("No posts found for bsky handle %s", handle)
            elif not initialized:
                for post in posts:
                    remember(post["uri"])
                save_seen_uris(seen_uris)
                initialized = True
                logger.info(
                    "Initialized bsky poller for %s at %d posts", handle, len(seen_uris)
                )
            else:
                for post in reversed(posts):
                    uri = post["uri"]
                    if uri in seen_set:
                        continue

                    remember(uri)
                    save_seen_uris(seen_uris)

                    try:
                        forward_post(bot, chat_ids, post)
                        logger.info("Forwarded bsky post %s to %s", uri, chat_ids)
                    except Exception as exc:
                        logger.error("Failed to forward bsky post %s: %s", uri, exc)
        except BskyRateLimitError as exc:
            logger.warning("Bsky rate limited for %s: %s", handle, exc)
        except Exception as exc:
            logger.error("Bsky polling failed for %s: %s", handle, exc)

        time.sleep(interval_seconds)


def fetch_latest_posts(handle: str, limit: int = 10) -> list[dict[str, Any]]:
    query = urlencode(
        {
            "actor": handle,
            "filter": "posts_no_replies",
            "limit": str(limit),
        }
    )
    url = f"{APPVIEW_BASE_URL}{AUTHOR_FEED_ENDPOINT}?{query}"
    response_data = fetch_json(url)

    posts = []
    for item in response_data.get("feed", []):
        if item.get("reason"):
            continue

        post = item.get("post") or {}
        record = post.get("record") or {}
        uri = post.get("uri")

        if not uri:
            continue

        if record.get("reply"):
            continue

        embed = post.get("embed")
        if not is_supported_embed(embed):
            logger.info("Skipped unsupported bsky post %s", uri)
            continue

        posts.append(
            {
                "uri": uri,
                "text": record.get("text", ""),
                "images": extract_image_urls(embed),
            }
        )

    return posts


def fetch_json(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise BskyRateLimitError("HTTP 429 from bsky API") from exc
        raise RuntimeError(f"HTTP {exc.code} from bsky API") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling bsky API: {exc.reason}") from exc


def extract_image_urls(embed: dict[str, Any] | None) -> list[str]:
    if not embed:
        return []

    embed_type = embed.get("$type", "")
    if embed_type.startswith("app.bsky.embed.images"):
        return [
            image["fullsize"]
            for image in embed.get("images", [])
            if image.get("fullsize")
        ]

    if embed_type.startswith("app.bsky.embed.recordWithMedia"):
        return extract_image_urls(embed.get("media"))

    return []


def is_supported_embed(embed: dict[str, Any] | None) -> bool:
    if not embed:
        return True

    embed_type = embed.get("$type", "")
    if embed_type.startswith("app.bsky.embed.images"):
        return True

    return False


def forward_post(bot, chat_ids: list[str], post: dict[str, Any]) -> None:
    text = html.unescape((post.get("text") or "").strip())
    images = post.get("images") or []

    for chat_id in chat_ids:
        if images:
            send_images(bot, chat_id, images, text)
        elif text:
            bot.send_message(chat_id, text)
        else:
            logger.info("Skipped empty bsky post %s for %s", post["uri"], chat_id)


def send_images(bot, chat_id: str, images: list[str], caption: str) -> None:
    if len(images) == 1:
        bot.send_photo(chat_id, images[0], caption=caption or None)
        return

    media = []
    for index, image_url in enumerate(images):
        if index == 0 and caption:
            media.append(types.InputMediaPhoto(image_url, caption=caption))
        else:
            media.append(types.InputMediaPhoto(image_url))

    bot.send_media_group(chat_id, media)
