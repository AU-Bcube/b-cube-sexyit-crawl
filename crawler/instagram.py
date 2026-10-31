import json
import logging
import random
import time

from instagrapi import Client

from .post import Post, to_post

log = logging.getLogger(__name__)

TIMELINE_QUERY = "IGProfileTimelineQuery"


class TimelineClient(Client):
    """instagrapi client whose profile timeline query can follow pagination logged out.

    instagrapi sends the next page as ``max_id``, which Instagram ignores for
    logged-out requests (the first page comes back every time). The query does
    honor ``profile_grid_items_cursor``, so it is swapped in here.
    """

    def __init__(self) -> None:
        super().__init__()
        self.request_timeout = 30
        self.grid_cursor: str | None = None
        self.last_timeline: dict = {}

    def private_graphql_request(self, data, *args, **kwargs):
        if data.get("fb_api_req_friendly_name") != TIMELINE_QUERY:
            return super().private_graphql_request(data, *args, **kwargs)
        variables = json.loads(data["variables"])
        variables.pop("max_id", None)
        if self.grid_cursor:
            variables["profile_grid_items_cursor"] = self.grid_cursor
        data = {**data, "variables": json.dumps(variables, separators=(",", ":"))}
        response = super().private_graphql_request(data, *args, **kwargs)
        self.last_timeline = self._find_profile_timeline_payload(response.get("data", response)) or {}
        return response


def fetch_all_posts(username: str) -> list[Post]:
    """Crawl every post of a public account without logging in, following pagination to the end.

    Raises if the result does not cover the account's full post count, so
    callers never act on a partial list.
    """
    cl = TimelineClient()
    user = cl.user_web_profile_info_v1(username)["user"]
    if user.get("is_private"):
        raise RuntimeError(f"@{username} is private; it cannot be crawled without login")
    user_id = int(user["id"])
    expected = user["edge_owner_to_timeline_media"]["count"]

    posts: dict[str, Post] = {}
    while True:
        medias, _ = cl._user_medias_paginated_app_gql(user_id)
        # Pinned posts can show up twice.
        new = [m for m in medias if m.code not in posts]
        posts.update((m.code, to_post(m)) for m in new)
        log.info("instagram: page +%d (%d/%d)", len(new), len(posts), expected)

        cursor = cl.last_timeline.get("profile_grid_items_cursor")
        if not cl.last_timeline.get("more_available") or not cursor:
            break
        # A page with nothing new means the cursor was ignored; stop instead of looping forever.
        if not new:
            raise RuntimeError("Instagram pagination is not advancing")
        cl.grid_cursor = cursor
        # Throttle page requests.
        time.sleep(random.uniform(2, 4))

    if len(posts) < expected:
        raise RuntimeError(f"Incomplete crawl: got {len(posts)} of {expected} posts")
    return list(posts.values())
