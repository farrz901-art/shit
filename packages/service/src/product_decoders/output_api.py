"""管理后台只读 API: 列 output/ 目录文件 + 读单个文件

设计原则:
- name 参数用 [a-zA-Z0-9._-]+ 字符集白名单, 防止路径越权
- (2026-06-16) D 集成: 后端选 local 时走本地 FS (保留老行为, 跟 pipeline.get_paths().output_dir 对齐);
  后端选 minio 时走 ObjectStore ABC, 返 {name, url, size, mime}.
- 文件大小上限 10 MB (local 模式, 防 OOM; minio 模式不限, presigned GET 流式)
"""

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.config.settings import settings
from src.storage.object_store import get_object_store

router = APIRouter(prefix="/api/output", tags=["output"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTS = {".md", ".json"}
SAFE_NAME = re.compile(r"^[a-zA-Z0-9._-]+$")


def _output_dir():
    """读 output_dir (ARCH-004: 改走 settings.paths.output_dir)"""
    return settings.paths.output_dir


def _backend_name() -> str:
    """读 store backend, 测试可 monkeypatch get_object_store"""
    return get_object_store().backend_name()


@router.get(
    "/files",
    summary="列产物文件 (.md / .json)",
    description=(
        "## 用途\n\n"
        "列出管理后台 ingest 产物目录下所有 .md / .json 文件, "
        "供前端产物浏览页用.\n\n"
        "## 鉴权\n\n"
        "无 (内部脚本 / 管理后台专用).\n\n"
        "## 行为\n\n"
        "按 mtime 倒序; 后端选 local 时读 get_paths().output_dir 本地 FS, "
        "后端选 minio 时走 ObjectStore ABC 拉 s3://{bucket}/outputs/ "
        "并返 {name, size, mtime}."
    ),
    responses={
        200: {"description": "返 {files: [{name, size, mtime}]}; mtime 倒序"},
    },
)
def list_files():
    """列 outputs/ 下 .md / .json 文件 (按 mtime 倒序)."""
    if _backend_name() == "local":
        # 本地 FS (跟旧行为 1:1, 兼容测试)
        output_dir = _output_dir()
        if not output_dir.exists():
            return {"files": []}
        items = []
        for p in sorted(output_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_file():
                continue
            if p.suffix.lower() not in ALLOWED_EXTS:
                continue
            if p.name.startswith("."):
                continue
            st = p.stat()
            items.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
        return {"files": items}

    # minio: 走 ABC
    store = get_object_store()
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
    prefix = f"s3://{bucket}/outputs/"
    items = []
    for meta in store.list_prefix(prefix):
        if Path(meta.uri).suffix.lower() not in ALLOWED_EXTS:
            continue
        if Path(meta.uri).name.startswith("."):
            continue
        items.append(
            {
                "name": Path(meta.uri).name,
                "size": meta.size,
                "mtime": meta.last_modified or 0.0,
            }
        )
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return {"files": items}


@router.get(
    "/files/{name}",
    summary="读单个产物文件",
    description=(
        "## 用途\n\n"
        "按文件名读单个 .md / .json 产物 (前端产物详情 / 预览用).\n\n"
        "## 鉴权\n\n"
        "无 (内部脚本 / 管理后台专用).\n\n"
        "## 行为\n\n"
        "name 走 SAFE_NAME 白名单 (^[a-zA-Z0-9._-]+$), 阻断路径越权; "
        "local backend 校验 is_relative_to(output_dir) 二次防御, "
        "越权 → 400; 文件 > 10 MB → 413; 不存在 → 404. "
        "local 返 {name, content, mime}; minio 返 {name, url, size, mime} "
        "(presigned GET URL)."
    ),
    responses={
        200: {"description": "local 返 {name, content, mime}; minio 返 {name, url, size, mime}"},
        400: {"description": "文件名非法 (不在白名单) 或路径越权"},
        404: {"description": "文件不存在"},
        413: {"description": "local 模式下文件超过 10 MB 上限"},
    },
)
def read_file(name: str):
    """读单个文件, 含 name 校验 + 大小校验 + 越权校验"""
    # 1. 字符白名单
    if not SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail=f"非法文件名: {name!r}")

    if _backend_name() == "local":
        # 2. 本地 FS 老路径
        output_dir = _output_dir().resolve()
        target = (output_dir / name).resolve()
        if not target.is_relative_to(output_dir):
            raise HTTPException(status_code=400, detail=f"路径越权: {name!r}")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
        size = target.stat().st_size
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件太大: {size} 字节 (上限 {MAX_FILE_SIZE} 字节 / 10 MB)",
            )
        suffix = target.suffix.lower()
        mime = {".md": "text/markdown", ".json": "application/json"}.get(suffix, "application/octet-stream")
        return {
            "name": name,
            "content": target.read_text(encoding="utf-8"),
            "mime": mime,
        }

    # minio: 走 ABC + presigned GET
    store = get_object_store()
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
    for meta in store.list_prefix(f"s3://{bucket}/outputs/"):
        if Path(meta.uri).name == name:
            url = store.presign_get(meta.uri)
            suffix = Path(name).suffix.lower()
            mime = {".md": "text/markdown", ".json": "application/json"}.get(suffix, "application/octet-stream")
            return {
                "name": name,
                "url": url,
                "size": meta.size,
                "mime": mime,
            }
    raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
