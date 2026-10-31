import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class R2Config:
    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    prefix: str
    public_base_url: str


@dataclass(frozen=True)
class Config:
    ig_target: str
    mongo_uri: str
    db_name: str
    r2: R2Config
    max_delete_ratio: float


def load_config(env: dict[str, str] | None = None) -> Config:
    env = dict(os.environ) if env is None else env
    missing: list[str] = []

    def required(name: str) -> str:
        value = (env.get(name) or "").strip()
        if not value:
            missing.append(name)
        return value

    values = {
        name: required(name)
        for name in (
            "IG_USERNAME",
            "DB_CONNECTION_STRING",
            "DB_NAME",
            "S3_ENDPOINT",
            "S3_PREFIX",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
            "S3_DEV_ACCESS_URL",
        )
    }
    # Report every missing variable at once instead of failing one per run.
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    # S3_ENDPOINT is "https://<account>.r2.cloudflarestorage.com/<bucket>".
    endpoint = urlparse(values["S3_ENDPOINT"])
    bucket = next((part for part in endpoint.path.split("/") if part), None)
    if not bucket:
        raise ValueError("S3_ENDPOINT must include the bucket name as its path")

    max_delete_ratio = float(env.get("MAX_DELETE_RATIO") or 0.5)
    if not 0 <= max_delete_ratio <= 1:
        raise ValueError("MAX_DELETE_RATIO must be between 0 and 1")

    return Config(
        ig_target=values["IG_USERNAME"],
        mongo_uri=values["DB_CONNECTION_STRING"],
        db_name=values["DB_NAME"],
        r2=R2Config(
            endpoint=f"{endpoint.scheme}://{endpoint.netloc}",
            bucket=bucket,
            access_key_id=values["S3_ACCESS_KEY_ID"],
            secret_access_key=values["S3_SECRET_ACCESS_KEY"],
            # "/sexyit2/" -> "sexyit2"
            prefix=values["S3_PREFIX"].strip("/"),
            public_base_url=values["S3_DEV_ACCESS_URL"].rstrip("/"),
        ),
        max_delete_ratio=max_delete_ratio,
    )
