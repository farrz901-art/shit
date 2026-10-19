"""ObjectStorage ABC + LocalFS + MinIO 实现 (2026-06-16 RAG 接入 MinIO spec)

所有存读删都走 ABC, 业务代码 (ingest / output_api / chat_share / eval) 不直接 import impl.

URI scheme:
- local://<relative_path>  (例: local://inputs/2026/foo.pdf)
- s3://<bucket>/<key>      (例: s3://rag-ingest/inputs/2026/foo.pdf)

设计原则:
- URI 字符串是 DB 持久化唯一形式 (B1 决策)
- 业务代码拿到 URI 调 ABC 操作, 不区分 backend
- presign() 只 Minio impl 真签 URL, LocalFS impl 返 None (业务可 fallback 走 backend 代理)
- 14 抽象方法 (跟 spec 6.3 / test_abc_has_14_abstract_methods 一致)
"""

from __future__ import annotations

import abc
import hashlib
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

import requests
from loguru import logger  # noqa: F401  跟 logging spec contract test (test_loguru_migration.py) 一致

from src.config.settings import settings

# botocore ClientError 用于结构化检查 NoSuchKey / 404. boto3 装必带, 防御性 fallback.
try:
    from botocore.exceptions import ClientError
except ImportError:
    # botocore 跟 boto3 一起装, 装 boto3 必带. 防御性 fallback (offline / 镜像不全场景).
    ClientError = None  # type: ignore[assignment,misc]


# ============== 错误模型 ==============


class ObjectStoreError(RuntimeError):
    """所有 backend 错误的基类."""


class ObjectNotFound(ObjectStoreError):
    """object 不存在. 业务显式处理, 走 404."""


# ============== URI helper ==============


_LOCAL_SCHEME = "local"
_S3_SCHEME = "s3"
# 默认 presigned URL 有效期 (秒). 短 TTL 防滥用, 业务可按需覆盖.
_DEFAULT_PRESIGN_TTL_SECONDS = 900


def parse_uri(uri: str) -> tuple[str, str]:
    """URI → (backend, key)
    's3://rag-ingest/inputs/abc/foo.pdf' → ('s3', 'inputs/abc/foo.pdf')
    'local://inputs/abc/foo.pdf' → ('local', 'inputs/abc/foo.pdf')
    raise ValueError on bad URI
    """
    p = urlparse(uri)
    if p.scheme not in (_LOCAL_SCHEME, _S3_SCHEME):
        raise ValueError(f"未知 URI scheme: {p.scheme!r} (uri={uri!r})")
    if p.scheme == _S3_SCHEME and not p.netloc:
        raise ValueError(f"s3 URI 缺 bucket: {uri!r}")
    # s3: netloc=bucket, path=/key → key 走 path.  local: 整段当 key (netloc+path).
    if p.scheme == _S3_SCHEME:
        key = p.path.lstrip("/")
    else:
        key = (p.netloc + p.path).lstrip("/")
    if not key:
        raise ValueError(f"URI 缺 key: {uri!r}")
    return p.scheme, key


def build_uri(backend: str, key: str, bucket: str | None = None) -> str:
    """反向: backend + key (+ bucket) → URI
    build_uri('local', 'inputs/foo.pdf') → 'local://inputs/foo.pdf'
    build_uri('s3', 'inputs/foo.pdf', 'rag-ingest') → 's3://rag-ingest/inputs/foo.pdf'
    """
    key = key.lstrip("/")
    if backend == _LOCAL_SCHEME:
        return f"{_LOCAL_SCHEME}://{key}"
    if backend == _S3_SCHEME:
        if not bucket:
            raise ValueError("s3 backend 必传 bucket")
        return f"{_S3_SCHEME}://{bucket}/{key}"
    raise ValueError(f"未知 backend: {backend!r}")


# ============== ObjectMeta ==============


@dataclass(frozen=True)
class ObjectMeta:
    """元数据 (不读 body)"""

    uri: str
    size: int
    mime: str | None = None
    last_modified: float | None = None  # epoch seconds


# ============== ABC ==============


class ObjectStore(abc.ABC):
    """对象存储 ABC. 14 抽象方法 (跟 spec 6.3 一致)."""

    @abc.abstractmethod
    def backend_name(self) -> str:
        """'local' / 'minio' / ... 供日志 / 调试用"""

    # ---- 写入 ----
    @abc.abstractmethod
    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None: ...
    @abc.abstractmethod
    def put_stream(self, uri: str, stream: BinaryIO, mime: str | None = None) -> None: ...
    @abc.abstractmethod
    def put_file(self, uri: str, src_path: str, mime: str | None = None) -> None: ...

    # ---- 读取 ----
    @abc.abstractmethod
    def get_bytes(self, uri: str) -> bytes: ...
    @abc.abstractmethod
    def get_stream(self, uri: str) -> BinaryIO: ...
    @abc.abstractmethod
    def open_local(self, uri: str) -> str: ...
    @abc.abstractmethod
    def release_local(self, local_path: str) -> None: ...

    @contextmanager
    def open_local_ctx(self, uri: str) -> Iterator[str]:
        path = self.open_local(uri)
        try:
            yield path
        finally:
            self.release_local(path)

    # ---- 列举 ----
    @abc.abstractmethod
    def list_prefix(self, prefix_uri: str) -> list[ObjectMeta]: ...
    @abc.abstractmethod
    def exists(self, uri: str) -> bool: ...
    @abc.abstractmethod
    def delete(self, uri: str) -> None: ...
    @abc.abstractmethod
    def delete_prefix(self, prefix_uri: str) -> None: ...

    # ---- Presigned URL ----
    @abc.abstractmethod
    def presign_put(self, uri: str, ttl_seconds: int = _DEFAULT_PRESIGN_TTL_SECONDS) -> str | None: ...
    @abc.abstractmethod
    def presign_get(self, uri: str, ttl_seconds: int = _DEFAULT_PRESIGN_TTL_SECONDS) -> str | None: ...


# ============== LocalFS impl ==============


class LocalFSObjectStore(ObjectStore):
    """LocalFS impl: 写本地 FS, key 直接当 LOCAL_ROOT 下相对路径."""

    def __init__(self, local_root: str | Path = "./ingest_uploads"):
        self._root = Path(local_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def backend_name(self) -> str:
        return "local"

    def _resolve(self, uri: str) -> Path:
        """URI → 绝对路径. 必须在 LOCAL_ROOT 下 (防越权)."""
        backend, key = parse_uri(uri)
        if backend != "local":
            raise ValueError(f"LocalFS impl 收到 non-local URI: {uri!r}")
        p = (self._root / key).resolve()
        if not p.is_relative_to(self._root):
            raise ValueError(f"URI 越权 (出 LOCAL_ROOT): {uri!r}")
        return p

    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None:
        p = self._resolve(uri)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def put_stream(self, uri: str, stream: BinaryIO, mime: str | None = None) -> None:
        p = self._resolve(uri)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as out:
            shutil.copyfileobj(stream, out)

    def put_file(self, uri: str, src_path: str, mime: str | None = None) -> None:
        p = self._resolve(uri)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, p)

    def get_bytes(self, uri: str) -> bytes:
        p = self._resolve(uri)
        if not p.exists():
            raise ObjectNotFound(f"object 不存在: {uri!r}")
        return p.read_bytes()

    def get_stream(self, uri: str) -> BinaryIO:
        p = self._resolve(uri)
        if not p.exists():
            raise ObjectNotFound(f"object 不存在: {uri!r}")
        return p.open("rb")

    def open_local(self, uri: str) -> str:
        """返 LOCAL_ROOT 下的绝对路径, 不复制."""
        return str(self._resolve(uri))

    def release_local(self, local_path: str) -> None:
        """LocalFS 不真删 (可能业务仍要用), no-op."""
        pass

    def list_prefix(self, prefix_uri: str) -> list[ObjectMeta]:
        backend, key = parse_uri(prefix_uri)
        if backend != "local":
            raise ValueError(f"LocalFS impl 收到 non-local URI: {prefix_uri!r}")
        prefix = self._root / key
        if not prefix.exists():
            return []
        out: list[ObjectMeta] = []
        for p in sorted(prefix.rglob("*")):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(self._root)
            except ValueError:
                continue
            uri = build_uri("local", str(rel).replace("\\", "/"))
            st = p.stat()
            out.append(ObjectMeta(uri=uri, size=st.st_size, last_modified=st.st_mtime))
        return out

    def exists(self, uri: str) -> bool:
        return self._resolve(uri).exists()

    def delete(self, uri: str) -> None:
        p = self._resolve(uri)
        p.unlink(missing_ok=True)

    def delete_prefix(self, prefix_uri: str) -> None:
        backend, key = parse_uri(prefix_uri)
        if backend != "local":
            raise ValueError(f"LocalFS impl 收到 non-local URI: {prefix_uri!r}")
        p = self._root / key
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    def presign_put(self, uri: str, ttl_seconds: int = _DEFAULT_PRESIGN_TTL_SECONDS) -> str | None:
        return None

    def presign_get(self, uri: str, ttl_seconds: int = _DEFAULT_PRESIGN_TTL_SECONDS) -> str | None:
        return None


# ============== Minio impl (Task 3 实现) ==============


class MinioObjectStore(ObjectStore):
    """MinIO impl: 走 boto3 S3 兼容协议.

    14 抽象方法 1:1 实现. lazy init: 不在 __init__ 调 MinIO, 第一次 put/list 时才连.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        use_ssl: bool = False,
        stage_root: str = "/tmp/minio_stage",
    ):
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._region = region
        self._use_ssl = use_ssl
        self._stage_root = Path(stage_root)
        self._stage_root.mkdir(parents=True, exist_ok=True)
        self._s3 = None  # lazy
        # (2026-06-17) open_local 借用表: uri → {refcount, path}. 同 uri 多次 open 复用同一文件, 引用计数 +1.
        self._borrowed: dict[str, dict[str, Any]] = {}

    @property
    def _client(self):
        """lazy boto3 client. boto3 client thread-safe (官方 v1.18+)."""
        if self._s3 is None:
            try:
                # 重依赖 lazy: boto3 + botocore 启动慢 (~600ms), LocalFS 路径不需要
                import boto3  # noqa: E402
                from botocore.client import Config  # noqa: E402
            except ImportError as e:
                raise ObjectStoreError("boto3 未装, 跑 uv add boto3") from e
            self._s3 = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )
        return self._s3

    def backend_name(self) -> str:
        return "minio"

    def _resolve(self, uri: str) -> str:
        """s3 URI → key. 验 URI 属 s3 scheme (防越权)."""
        backend, key = parse_uri(uri)
        if backend != "s3":
            raise ValueError(f"Minio impl 收到 non-s3 URI: {uri!r}")
        return key

    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None:
        key = self._resolve(uri)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=mime or "application/octet-stream",
            )
        except Exception as e:
            if (ClientError is not None and isinstance(e, ClientError)) or isinstance(
                e, (requests.RequestException, OSError)
            ):
                raise ObjectStoreError(f"put_bytes 失败: {e}") from e
            raise

    def put_stream(self, uri: str, stream: BinaryIO, mime: str | None = None) -> None:
        key = self._resolve(uri)
        try:
            extra: dict | None = {"ContentType": mime} if mime else None
            if extra:
                self._client.upload_fileobj(stream, self._bucket, key, ExtraArgs=extra)
            else:
                # boto3 upload_fileobj 不接 ExtraArgs=None
                self._client.upload_fileobj(stream, self._bucket, key)
        except Exception as e:
            if (ClientError is not None and isinstance(e, ClientError)) or isinstance(
                e, (requests.RequestException, OSError)
            ):
                raise ObjectStoreError(f"put_stream 失败: {e}") from e
            raise

    def put_file(self, uri: str, src_path: str, mime: str | None = None) -> None:
        key = self._resolve(uri)
        try:
            extra: dict = {"ContentType": mime} if mime else {}
            self._client.upload_file(src_path, self._bucket, key, ExtraArgs=extra)
        except Exception as e:
            if (ClientError is not None and isinstance(e, ClientError)) or isinstance(
                e, (requests.RequestException, OSError)
            ):
                raise ObjectStoreError(f"put_file 失败: {e}") from e
            raise

    def get_bytes(self, uri: str) -> bytes:
        key = self._resolve(uri)
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as e:
            # 优先用 ClientError.response["Error"]["Code"] 结构化检查, fallback 到 str 子串 (防御性)
            is_not_found = False
            if ClientError is not None and isinstance(e, ClientError):
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "NoSuchVersion", "404"):
                    is_not_found = True
            elif "NoSuchKey" in str(e) or "404" in str(e):
                is_not_found = True
            if is_not_found:
                raise ObjectNotFound(f"object 不存在: {uri!r}") from e
            raise ObjectStoreError(f"get_bytes 失败: {e}") from e

    def get_stream(self, uri: str) -> BinaryIO:
        key = self._resolve(uri)
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            # boto3 返 StreamingBody, 在功能上是 BinaryIO, 这里接受 .read()
            return resp["Body"]  # type: ignore[return-value]
        except Exception as e:
            # 优先用 ClientError.response["Error"]["Code"] 结构化检查, fallback 到 str 子串 (防御性)
            is_not_found = False
            if ClientError is not None and isinstance(e, ClientError):
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "NoSuchVersion", "404"):
                    is_not_found = True
            elif "NoSuchKey" in str(e) or "404" in str(e):
                is_not_found = True
            if is_not_found:
                raise ObjectNotFound(f"object 不存在: {uri!r}") from e
            raise ObjectStoreError(f"get_stream 失败: {e}") from e

    def open_local(self, uri: str) -> str:
        """下载到 stage dir, 返 local path. 同 uri 多次开复用同一文件, 引用计数 +1."""
        # 缓存分支: 同一 uri 已借出过, 直接返缓存 path + 引用计数 +1 (避免重复下载, 不重复 unlink)
        if uri in self._borrowed:
            self._borrowed[uri]["refcount"] += 1
            return self._borrowed[uri]["path"]
        key = self._resolve(uri)
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        local_dir = self._stage_root / key_hash
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / Path(key).name
        try:
            self._client.download_file(self._bucket, key, str(local_path))
        except Exception as e:
            # 优先用 ClientError.response["Error"]["Code"] 结构化检查, fallback 到 str 子串 (防御性)
            is_not_found = False
            if ClientError is not None and isinstance(e, ClientError):
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "NoSuchVersion", "404"):
                    is_not_found = True
            elif "NoSuchKey" in str(e) or "404" in str(e):
                is_not_found = True
            if is_not_found:
                raise ObjectNotFound(f"object 不存在: {uri!r}") from e
            raise ObjectStoreError(f"download 失败: {e}") from e
        self._borrowed[uri] = {"refcount": 1, "path": str(local_path)}
        return str(local_path)

    def release_local(self, local_path: str) -> None:
        """引用计数 -1, 归 0 删文件 + 删 _borrowed entry. 简化实现."""
        # 反查: 找 _borrowed[uri]["path"] == local_path 的 entry
        for uri, entry in list(self._borrowed.items()):
            if entry["path"] == local_path:
                entry["refcount"] -= 1
                if entry["refcount"] <= 0:
                    try:
                        Path(local_path).unlink(missing_ok=True)
                    except OSError:
                        pass
                    del self._borrowed[uri]
                return
        # 找不到 entry: 说明 open_local 没走过这 path 或已 release 完, no-op
        pass

    def list_prefix(self, prefix_uri: str) -> list[ObjectMeta]:
        backend, key = parse_uri(prefix_uri)
        if backend != "s3":
            raise ValueError(f"Minio impl 收到 non-s3 URI: {prefix_uri!r}")
        # 分页: boto3 list_objects_v2 单页 ≤ 1000, 大 prefix 必须用 ContinuationToken 翻页
        out: list[ObjectMeta] = []
        token: str | None = None
        try:
            while True:
                kwargs: dict = {"Bucket": self._bucket, "Prefix": key}
                if token:
                    kwargs["ContinuationToken"] = token
                resp = self._client.list_objects_v2(**kwargs)
                for obj in resp.get("Contents", []):
                    # boto3 TypedDict ObjectTypeDef 标 Key/Size/LastModified 为 not-required,
                    # 但 list_objects_v2 实际总返, 这里 type: ignore 绕开严格检查
                    obj_key = obj["Key"]  # type: ignore[index]
                    full_uri = build_uri("s3", obj_key, bucket=self._bucket)
                    lm = obj.get("LastModified")
                    out.append(
                        ObjectMeta(
                            uri=full_uri,
                            size=obj.get("Size") or 0,
                            mime=None,  # boto3 list_objects_v2 不返 ContentType
                            last_modified=lm.timestamp() if lm is not None else None,  # type: ignore[union-attr]
                        )
                    )
                token = resp.get("NextContinuationToken")
                if not token:
                    break
        except Exception as e:
            raise ObjectStoreError(f"list_objects_v2 失败: {e}") from e
        return out

    def exists(self, uri: str) -> bool:
        key = self._resolve(uri)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception as e:
            # 优先用 ClientError.response["Error"]["Code"] 结构化检查, fallback 到 str 子串 (防御性)
            is_not_found = False
            if ClientError is not None and isinstance(e, ClientError):
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "NoSuchVersion", "404", "NotFound"):
                    is_not_found = True
            elif "404" in str(e):
                is_not_found = True
            if is_not_found:
                return False
            raise ObjectStoreError(f"head_object 失败: {e}") from e

    def delete(self, uri: str) -> None:
        key = self._resolve(uri)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as e:
            raise ObjectStoreError(f"delete_object 失败: {e}") from e

    def delete_prefix(self, prefix_uri: str) -> None:
        backend, key = parse_uri(prefix_uri)
        if backend != "s3":
            raise ValueError(f"Minio impl 收到 non-s3 URI: {prefix_uri!r}")
        # 分页: 同一 list_objects_v2 翻页原因, 否则 >1000 objects 漏删
        try:
            token: str | None = None
            while True:
                kwargs: dict = {"Bucket": self._bucket, "Prefix": key}
                if token:
                    kwargs["ContinuationToken"] = token
                resp = self._client.list_objects_v2(**kwargs)
                for obj in resp.get("Contents", []):
                    # boto3 TypedDict 标 Key 为 not-required, 实际总有, type: ignore 绕开
                    self._client.delete_object(Bucket=self._bucket, Key=obj["Key"])  # type: ignore[index]
                token = resp.get("NextContinuationToken")
                if not token:
                    break
        except Exception as e:
            raise ObjectStoreError(f"delete_prefix 失败: {e}") from e

    def presign_put(self, uri: str, ttl_seconds: int = _DEFAULT_PRESIGN_TTL_SECONDS) -> str | None:
        key = self._resolve(uri)
        try:
            return self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except Exception as e:
            raise ObjectStoreError(f"presign_put 失败: {e}") from e

    def presign_get(self, uri: str, ttl_seconds: int = _DEFAULT_PRESIGN_TTL_SECONDS) -> str | None:
        key = self._resolve(uri)
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except Exception as e:
            raise ObjectStoreError(f"presign_get 失败: {e}") from e


# ============== 单例工厂 (env 切 backend) ==============


_object_store_singleton: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    """读 env 返单例. env OBJECT_STORE_BACKEND=local (默认) | minio.

    - local: 走 LocalFSObjectStore, root 从 OBJECT_STORE_LOCAL_ROOT 读
    - minio: 走 MinioObjectStore, 从 OBJECT_STORE_S3_* 读 (Task 3 完整实现)
    """
    global _object_store_singleton
    if _object_store_singleton is not None:
        return _object_store_singleton
    backend = settings.object_store_backend
    if backend == "local":
        root = settings.object_store_local_root
        _object_store_singleton = LocalFSObjectStore(local_root=root)
    elif backend == "minio":
        # Task 3 完整实现, 当前 Task 2 先 import 以暴露
        endpoint = settings.object_store_s3_endpoint
        access_key = settings.object_store_s3_access_key
        secret_key = settings.object_store_s3_secret_key
        bucket = settings.object_store_s3_bucket
        region = settings.object_store_s3_region
        use_ssl = settings.object_store_s3_use_ssl.lower() == "true"
        stage_root = settings.object_store_stage_root
        _object_store_singleton = MinioObjectStore(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            region=region,
            use_ssl=use_ssl,
            stage_root=stage_root,
        )
    else:
        raise ValueError(f"未知 OBJECT_STORE_BACKEND: {backend!r}")
    return _object_store_singleton


def _reset_object_store() -> None:
    """清单例. 仅测试用, 允许不同 case 切 env 后重建."""
    global _object_store_singleton
    _object_store_singleton = None
