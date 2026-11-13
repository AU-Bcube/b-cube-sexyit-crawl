from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from crawler.config import load_config
from crawler.instagram import fetch_first_page_posts
from crawler.post import Post, extract_title, to_post
from crawler.r2 import image_download_session
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


def test_fetch_first_page_posts_skips_profile_lookup_and_stops_after_one_page(monkeypatch):
    profile_html = (
        '"resource":{"__dr":"PolarisProfilePostsTabRoot.react"},'
        '"props":{"id":"123"}'
    )
    profile_requests = []

    class FakeResponse:
        text = profile_html

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, proxies=None):
        profile_requests.append((url, timeout, proxies))
        return FakeResponse()

    monkeypatch.setattr("crawler.instagram.requests.get", fake_get)

    timeline_requests = []

    class FakeClient:
        def _user_medias_paginated_app_gql(self, user_id, amount):
            timeline_requests.append((user_id, amount))
            return [media()], "next-page-cursor"

    monkeypatch.setattr("crawler.instagram.Client", FakeClient)
    assert [p.ig_post_id for p in fetch_first_page_posts("target")] == ["ABC"]
    assert profile_requests == [("https://www.instagram.com/target/", 30, None)]
    assert timeline_requests == [("123", 12)]


def test_fetch_first_page_posts_routes_both_instagram_requests_through_proxy(monkeypatch):
    proxy = "http://user:pass@proxy:8080"
    profile_proxies = []

    class FakeResponse:
        text = '"resource":{"__dr":"PolarisProfilePostsTabRoot.react"},"props":{"id":"123"}'

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, proxies=None):
        profile_proxies.append(proxies)
        return FakeResponse()

    monkeypatch.setattr("crawler.instagram.requests.get", fake_get)

    client_proxies = []

    class FakeClient:
        def set_proxy(self, dsn):
            client_proxies.append(dsn)

        def _user_medias_paginated_app_gql(self, user_id, amount):
            return [media()], None

    monkeypatch.setattr("crawler.instagram.Client", FakeClient)
    fetch_first_page_posts("target", proxy)
    assert profile_proxies == [{"http": proxy, "https": proxy}]
    assert client_proxies == [proxy]


def test_image_download_session_ignores_proxy_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:8080")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:8080")
    session = image_download_session()
    assert session.trust_env is False
    assert session.proxies == {}
    settings = session.merge_environment_settings("https://scontent.cdninstagram.com/x.jpg", {}, None, None, None)
    assert not settings["proxies"]


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


def test_partial_snapshot_never_deletes_stored_posts():
    plan = plan_sync(["old", "current"], [post("current", 1)], 0.5, complete_snapshot=False)
    assert plan.to_delete == []


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
    assert config.ig_proxy_url is None
    assert load_config(env | {"IG_PROXY_URL": " http://p:1 "}).ig_proxy_url == "http://p:1"

    with pytest.raises(ValueError, match="IG_USERNAME, DB_NAME, S3_ACCESS_KEY_ID"):
        load_config(env | {"IG_USERNAME": "", "DB_NAME": "", "S3_ACCESS_KEY_ID": ""})
