from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .post import Post

# Below this many deletions the ratio guard is skipped, so removing 1 of 2 posts still works.
MIN_DELETIONS_FOR_RATIO_GUARD = 3


@dataclass(frozen=True)
class SyncPlan:
    to_add: list[Post]
    to_delete: list[str]
    # New posts left out because their caption has no hashtag to use as a title.
    skipped: list[str]


def plan_sync(
    stored_ids: Iterable[str],
    crawled: Sequence[Post],
    max_delete_ratio: float,
    *,
    complete_snapshot: bool = True,
) -> SyncPlan:
    """Diff the crawled posts against what is stored.

    When ``complete_snapshot`` is false, missing IDs are retained because the
    result may contain only one page. Empty results still fail if the DB has
    posts, since that can indicate a blocked or broken crawl.
    """
    stored = set(stored_ids)
    live = {post.ig_post_id: post for post in crawled}

    new = [post for post_id, post in live.items() if post_id not in stored]
    to_add = [post for post in new if post.title]
    skipped = [post.ig_post_id for post in new if not post.title]
    to_delete = sorted(stored - live.keys()) if complete_snapshot else []

    if stored and not live:
        raise RuntimeError("Crawl returned 0 posts but the DB has posts; refusing to delete anything")
    if len(to_delete) >= MIN_DELETIONS_FOR_RATIO_GUARD and len(to_delete) / len(stored) > max_delete_ratio:
        raise RuntimeError(
            f"Would delete {len(to_delete)}/{len(stored)} posts (> {max_delete_ratio:.0%}); "
            "refusing, crawl is likely incomplete"
        )
    return SyncPlan(to_add=to_add, to_delete=to_delete, skipped=skipped)
