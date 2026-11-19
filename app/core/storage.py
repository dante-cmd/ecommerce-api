import io
import json

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _get_s3_client(settings: Settings):
    endpoint_url = f"{'https' if settings.rustfs_use_ssl else 'http'}://{settings.rustfs_endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.rustfs_access_key,
        aws_secret_access_key=settings.rustfs_secret_key,
        config=Config(signature_version="s3v4"),
    )


def _public_read_policy(bucket: str) -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadObjects",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
    )


def ensure_bucket(settings: Settings) -> None:
    client = _get_s3_client(settings)
    try:
        client.head_bucket(Bucket=settings.rustfs_bucket_name)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in {"404", "NoSuchBucket"}:
            client.create_bucket(Bucket=settings.rustfs_bucket_name)
        else:
            raise
    # Objects are served through public URLs, so keep the bucket anonymously readable.
    client.put_bucket_policy(
        Bucket=settings.rustfs_bucket_name,
        Policy=_public_read_policy(settings.rustfs_bucket_name),
    )


def upload_file(
    file_bytes: bytes, key: str, content_type: str = "application/octet-stream"
) -> str:
    settings = get_settings()
    client = _get_s3_client(settings)
    ensure_bucket(settings)
    client.put_object(
        Bucket=settings.rustfs_bucket_name,
        Key=key,
        Body=io.BytesIO(file_bytes),
        ContentType=content_type,
    )
    return f"{'https' if settings.rustfs_use_ssl else 'http'}://{settings.rustfs_endpoint}/{settings.rustfs_bucket_name}/{key}"


def delete_file(key: str) -> None:
    settings = get_settings()
    client = _get_s3_client(settings)
    try:
        client.delete_object(Bucket=settings.rustfs_bucket_name, Key=key)
    except ClientError:
        logger.warning("Failed to delete object", key=key)


def get_public_url(key: str) -> str:
    settings = get_settings()
    return f"{'https' if settings.rustfs_use_ssl else 'http'}://{settings.rustfs_endpoint}/{settings.rustfs_bucket_name}/{key}"
