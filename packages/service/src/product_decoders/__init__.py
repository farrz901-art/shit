"""product_decoders package

通用产品订货号解析 (FastAPI 服务 + 配置驱动).
"""

from .config_loader import ConfigLoader
from .engine import ProductDecoder
from .router import router

__all__ = ["ConfigLoader", "ProductDecoder", "router"]
