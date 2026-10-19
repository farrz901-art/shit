"""配置加载器: 按需加载 + 缓存"""

from pathlib import Path

import yaml


class ConfigLoader:
    """配置加载器, 支持按需加载和缓存

    用法:
        loader = ConfigLoader(config_dir="configs")
        cfg = loader.load("siemens_1le0_low_voltage")
    """

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self._cache: dict[str, dict] = {}

    def load(self, series_id: str) -> dict:
        """按 series_id 加载单个配置 (缓存)"""
        if series_id in self._cache:
            return self._cache[series_id]
        for yaml_file in self.config_dir.rglob("*.yaml"):
            with open(yaml_file, encoding="utf-8") as f:
                cfg = _safe_yaml_load(f)
            if cfg and cfg.get("series") == series_id:
                self._cache[series_id] = cfg
                return cfg
        raise ValueError(f"未找到系列配置: {series_id}")

    def load_all(self) -> list[dict]:
        """加载目录下所有 yaml 配置"""
        configs: list[dict] = []
        for yaml_file in self.config_dir.rglob("*.yaml"):
            with open(yaml_file, encoding="utf-8") as f:
                cfg = _safe_yaml_load(f)
            if cfg:
                configs.append(cfg)
        return configs


def _safe_yaml_load(f) -> dict:
    """读 yaml 时容错: 空文件 / 注释-only 文件返回 None"""
    cfg = yaml.safe_load(f)
    return cfg or {}
