from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from crawler.config import load_config
from crawler.post import Post, extract_title, to_post
from crawler.sync import plan_sync

BASE = datetime(2026, 10, 1, tzinfo=UTC)


def day(n: int) -> datetime:
    return BASE + timedelta(days=n)


def post(post_id: str, n: int, title: str = "t") -> Post:
    return Post(ig_post_id=post_id, date=day(n), title=title, image_url="u", url="")


def media(**fields):
    defaults = dict(code="ABC", taken_at=BASE, caption_text="", media_type=1, thumbnail_url=None, resources=[])
    return SimpleNamespace(**(defaults | fields))


def test_extract_title_takes_first_hashtag_anywhere():
    assert extract_title("오늘의 글 #휴머노이드_로봇 and #second") == "휴머노이드_로봇"
    assert extract_title("#first") == "first"
    assert extract_title("no tags here") == ""
    assert extract_title(None) == ""


def test_to_post_maps_single_image():
    p = to_post(media(caption_text="hi #tag", thumbnail_url="https://cdn/big.jpg"))
    assert p == Post(ig_post_id="ABC", date=BASE, title="tag", image_url="https://cdn/big.jpg",
                     url="https://www.instagram.com/p/ABC/")


def test_to_post_uses_first_album_item():
    p = to_post(media(media_type=8, resources=[
        SimpleNamespace(thumbnail_url="https://cdn/first.jpg"),
        SimpleNamespace(thumbnail_url="https://cdn/second.jpg"),
    ]))
    assert p.image_url == "https://cdn/first.jpg"


def test_adds_new_and_deletes_removed():
    plan = plan_sync(["b", "c", "d"], [post("a", 3), post("b", 2), post("c", 1)], 0.5)
    assert [p.ig_post_id for p in plan.to_add] == ["a"]
    assert plan.to_delete == ["d"]


def test_skips_new_posts_without_hashtag():
    plan = plan_sync([], [post("a", 2), post("untitled", 1, title="")], 0.5)
    assert [p.ig_post_id for p in plan.to_add] == ["a"]
    assert plan.skipped == ["untitled"]
    assert plan.to_delete == []


def test_dedupes_posts_listed_twice():
    assert len(plan_sync([], [post("a", 1), post("a", 1)], 0.5).to_add) == 1


def test_allows_small_deletions():
    assert plan_sync(["a", "b"], [post("a", 1)], 0.5).to_delete == ["b"]


def test_refuses_empty_or_suspicious_crawl():
    with pytest.raises(RuntimeError):
        plan_sync(["a"], [], 0.5)
    with pytest.raises(RuntimeError):
        plan_sync(["a", "b", "c", "d"], [post("a", 1)], 0.5)
    assert plan_sync([], [], 0.5).to_add == []


def test_load_config_parses_r2_and_reports_all_missing():
    env = {
        "IG_USERNAME": "t", "DB_CONNECTION_STRING": "mongodb://x", "DB_NAME": "bcube",
        "S3_ENDPOINT": "https://acc.r2.cloudflarestorage.com/bcube", "S3_PREFIX": "/sexyit2/",
        "S3_ACCESS_KEY_ID": "k", "S3_SECRET_ACCESS_KEY": "s", "S3_DEV_ACCESS_URL": "https://pub.r2.dev/",
    }
    config = load_config(env)
    assert (config.r2.endpoint, config.r2.bucket, config.r2.prefix) == (
        "https://acc.r2.cloudflarestorage.com", "bcube", "sexyit2")
    assert config.r2.public_base_url == "https://pub.r2.dev"
    assert config.db_name == "bcube"

    with pytest.raises(ValueError, match="IG_USERNAME, DB_NAME, S3_ACCESS_KEY_ID"):
        load_config(env | {"IG_USERNAME": "", "DB_NAME": "", "S3_ACCESS_KEY_ID": ""})
