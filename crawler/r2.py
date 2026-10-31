import boto3
import requests

from .config import R2Config

EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic"}


class R2Uploader:
    def __init__(self, config: R2Config, http: requests.Session) -> None:
        self._config = config
        self._http = http
        self._s3 = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="auto",
        )

    def upload_image(self, image_url: str, name: str) -> str:
        """Copy the image into R2 and return its public URL. Re-uploading the same name overwrites."""
        res = self._http.get(image_url, timeout=30)
        res.raise_for_status()
        content_type = res.headers.get("content-type", "").split(";")[0].strip()
        ext = EXT_BY_TYPE.get(content_type)
        if not ext:
            raise ValueError(f"Unexpected image content-type: {content_type or '(none)'}")

        key = f"{self._config.prefix}/{name}.{ext}"
        self._s3.put_object(Bucket=self._config.bucket, Key=key, Body=res.content, ContentType=content_type)
        return f"{self._config.public_base_url}/{key}"
