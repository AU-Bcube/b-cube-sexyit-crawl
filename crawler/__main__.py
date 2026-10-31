import logging
import sys

import requests
from pymongo import ASCENDING, MongoClient

from .config import load_config
from .instagram import fetch_all_posts
from .r2 import R2Uploader
from .sync import plan_sync

log = logging.getLogger("crawler")


def run() -> int:
    config = load_config()
    with MongoClient(config.mongo_uri, tz_aware=True) as mongo, requests.Session() as http:
        posts = mongo[config.db_name]["sexyits2"]
        posts.create_index([("ig_post_id", ASCENDING)], unique=True)

        stored_ids = posts.distinct("ig_post_id")
        crawled = fetch_all_posts(config.ig_target)
        log.info("stored=%d crawled=%d", len(stored_ids), len(crawled))

        plan = plan_sync(stored_ids, crawled, config.max_delete_ratio)
        if plan.skipped:
            log.info("skipped %d posts without a hashtag: %s", len(plan.skipped), ", ".join(plan.skipped))
        uploader = R2Uploader(config.r2, http)

        added = failed = 0
        for post in plan.to_add:
            try:
                if not post.image_url:
                    raise ValueError("no image url")
                image_path = uploader.upload_image(post.image_url, post.ig_post_id)
                # Upsert so a run that crashed after uploading can be safely retried.
                posts.update_one(
                    {"ig_post_id": post.ig_post_id},
                    {"$setOnInsert": {"date": post.date, "title": post.title, "imagePath": image_path, "url": post.url}},
                    upsert=True,
                )
                added += 1
                log.info("added %s", post.ig_post_id)
            except Exception:
                failed += 1
                log.exception("failed %s", post.ig_post_id)

        # Deleted on Instagram -> remove from MongoDB only; R2 objects are kept.
        deleted = 0
        if plan.to_delete:
            deleted = posts.delete_many({"ig_post_id": {"$in": plan.to_delete}}).deleted_count

        log.info("done: added=%d deleted=%d failed=%d", added, deleted, failed)
        return 1 if failed else 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(run())


if __name__ == "__main__":
    main()
