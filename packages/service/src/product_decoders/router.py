"""product_decoders/router.py (2026-06-23)

从 app.py 的 create_app() 提取 /decode, /series, /product-decoder/health 三个端点至独立 router.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .config_loader import ConfigLoader
from .engine import ProductDecoder

# 配置目录优先级: 环境变量 PRODUCT_DECODERS_CONFIGS > 默认根目录 configs/product_decoders/
# 默认值用 __file__ 解析, 不依赖 CWD
_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "product_decoders"
_CONFIGS_DIR = Path(os.environ.get("PRODUCT_DECODERS_CONFIGS", str(_CONFIGS_DIR)))
_loader = ConfigLoader(config_dir=str(_CONFIGS_DIR))
_decoder = ProductDecoder(_loader)

router = APIRouter(tags=["product-decoder"])


class DecodeRequest(BaseModel):
    """解码请求"""

    model: str = Field(..., description="完整订货号, 如 1LE0001-1AA42-1AA4")


class SeriesInfo(BaseModel):
    """系列信息"""

    series: str = Field(..., description="产品系列代号")
    manufacturer: str = Field(..., description="厂商")
    name: str = Field(..., description="显示名")
    prefix: str = Field(..., description="订货号前缀")


@router.post(
    "/decode",
    summary="解码订货号",
    description=(
        "## 用途\n\n"
        "把完整产品订货号解析为结构化字段 + LLM 友好视图, 供 Dify 工作流调用.\n\n"
        "## 鉴权\n\n"
        "无 (Dify 内部脚本专用, 不依赖 `CurrentUser`).\n\n"
        "## 行为\n\n"
        "- 输入: 完整订货号, 例 `1LE0001-1AA42-1AA4`\n"
        "- 输出: 结构化字段 (model/series/...) + `llm_view` 字符串\n"
        "- 解析不识别: 抛 400 (ValueError)\n"
        "- 内部异常: 抛 500, detail 含原始错误信息"
    ),
)
async def decode(req: DecodeRequest):
    """解码产品订货号"""
    try:
        result = _decoder.decode(req.model)
        result["llm_view"] = _decoder.build_llm_view(result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内部错误: {e}")


@router.get(
    "/series",
    response_model=list[SeriesInfo],
    summary="列出支持的产品系列",
    description=(
        "## 用途\n\n"
        "列出当前配置文件里注册的所有产品系列元信息.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "- 返 list, 每项含 `series` / `manufacturer` / `name` / `prefix`\n"
        "- 顺序与配置加载顺序一致, 无分页"
    ),
)
async def list_series():
    """列出所有产品系列"""
    return _decoder.list_series()


@router.get(
    "/product-decoder/health",
    summary="解码服务 health",
    description=(
        "## 用途\n\n"
        "解码服务存活检查 + 序列数量.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        '- 返 `{status: "ok", series_count: int}`\n'
        "- 跟 `/api/health/system` 区别: 本端点只检查解码器, 不检查外部依赖"
    ),
)
async def decoder_health():
    """解码服务健康检查"""
    return {"status": "ok", "series_count": len(_decoder.list_series())}
