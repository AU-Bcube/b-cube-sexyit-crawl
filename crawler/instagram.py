import logging
import re

import requests
from instagrapi import Client

from .post import Post, to_post

log = logging.getLogger(__name__)

FIRST_PAGE_SIZE = 12
PROFILE_POSTS_ROOT_USER_ID = re.compile(
    r'"resource":\{"__dr":"PolarisProfilePostsTabRoot\.react"\},"props":\{"id":"(?P<user_id>\d+)"'
)


def _public_profile_user_id(username: str) -> str:
    response = requests.get(f"https://www.instagram.com/{username}/", timeout=30)
    response.raise_for_status()
    match = PROFILE_POSTS_ROOT_USER_ID.search(response.text)
    if not match:
        raise RuntimeError(f"Could not find Instagram user ID in @{username}'s public profile page")
    return match.group("user_id")


def fetch_first_page_posts(username: str) -> list[Post]:
    """Fetch only the first page of posts from a public profile without logging in."""
    user_id = _public_profile_user_id(username)
    client = Client()
    client.request_timeout = 30
    medias, _ = client._user_medias_paginated_app_gql(user_id, amount=FIRST_PAGE_SIZE)
    log.info("instagram: fetched first page (%d posts)", len(medias))
    return [to_post(media) for media in medias]
