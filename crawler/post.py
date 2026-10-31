import re
from dataclasses import dataclass
from datetime import datetime

from instagrapi.types import Media

# Word characters cover Hangul, other letters, digits and underscore.
HASHTAG = re.compile(r"#(\w+)")


@dataclass(frozen=True)
class Post:
    ig_post_id: str
    date: datetime
    title: str
    image_url: str | None
    url: str


def extract_title(caption: str | None) -> str:
    """First hashtag anywhere in the caption, without the leading '#'."""
    match = HASHTAG.search(caption or "")
    return match.group(1) if match else ""


def best_image_url(media: Media) -> str | None:
    """Highest-resolution image of the post; for albums, of the first item.

    instagrapi already resolves ``thumbnail_url`` to the largest candidate
    (for videos this is the cover image).
    """
    source = media.resources[0] if media.media_type == 8 and media.resources else media
    return str(source.thumbnail_url) if source.thumbnail_url else None


def to_post(media: Media) -> Post:
    return Post(
        ig_post_id=media.code,
        date=media.taken_at,
        title=extract_title(media.caption_text),
        image_url=best_image_url(media),
        url=f"https://www.instagram.com/p/{media.code}/",
    )
