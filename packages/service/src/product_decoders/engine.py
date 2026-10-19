"""产品订货号解析引擎

按 model 前缀路由到不同 YAML 配置, 按 char_count 顺序消耗字符.
"""

import re

from .config_loader import ConfigLoader


class ProductDecoder:
    """产品型号解码器核心

    关键设计: 每个 position 有 char_count, 解析器按 char_count 顺序消耗字符.
    加新系列只需写 YAML, 零代码改动.

    用法:
        loader = ConfigLoader(config_dir="configs")
        decoder = ProductDecoder(loader)
        result = decoder.decode("1LE0001-1AA4-21-AA4")
    """

    def __init__(self, loader: ConfigLoader):
        self.loader = loader
        self._routing_table: list[dict] | None = None

    # ------------------------------------------------------------------
    # 路由器
    # ------------------------------------------------------------------
    def _build_routing_table(self) -> list[dict]:
        if self._routing_table is not None:
            return self._routing_table
        configs = self.loader.load_all()
        table = []
        for cfg in configs:
            router = cfg.get("router", {})
            table.append(
                {
                    "series": cfg["series"],
                    "prefix": router.get("prefix", ""),
                    "pattern": router.get("pattern", ""),
                    "priority": router.get("priority", 0),
                }
            )
        table.sort(key=lambda x: (-x["priority"], -len(x["prefix"])))
        self._routing_table = table
        return table

    def route(self, model: str) -> str:
        normalized = self._normalize(model)
        for entry in self._build_routing_table():
            pattern = entry["pattern"] or f"^{entry['prefix']}"
            if re.match(pattern, normalized):
                return entry["series"]
        raise ValueError(f"无法识别型号所属系列: {model}")

    # ------------------------------------------------------------------
    # 标准化
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(model: str) -> str:
        return model.replace("-", "").replace(" ", "").upper()

    # ------------------------------------------------------------------
    # 核心解码 (变长位置支持)
    # ------------------------------------------------------------------
    def decode(self, model: str) -> dict:
        series_id = self.route(model)
        cfg = self.loader.load(series_id)

        raw = self._normalize(model)
        expected_len = cfg["decoder"]["total_chars"]

        result = {
            "series": series_id,
            "series_name": cfg.get("series_name_zh", ""),
            "manufacturer": cfg.get("manufacturer", ""),
            "raw_input": model,
            "normalized": raw,
        }

        # 容错: 标准化后可能比 expected_len 长 (型号带后缀, 如 1LE0001-1AA42-1AA4-Z F40)
        # 截取前 expected_len 字符, 后缀进 _suffix
        if len(raw) > expected_len:
            result["_suffix"] = raw[expected_len:]
            result["normalized"] = raw[:expected_len]
            raw = raw[:expected_len]
        elif len(raw) < expected_len:
            raise ValueError(
                f"型号长度错误: {model} → 标准化后 {len(raw)} 位, 期望 {expected_len} 位 (系列: {series_id})"
            )

        # 按 char_count 顺序消耗字符
        cursor = 0
        warnings: list[dict] = []

        for pos in cfg["decoder"]["positions"]:
            char_count = pos.get("char_count", 1)
            segment = raw[cursor : cursor + char_count]
            cursor += char_count

            pos_name = pos["name"]
            pos_type = pos.get("type", "enum")

            # ----- 固定值前缀位 (如 1LE000) -----
            if pos_type == "fixed":
                expected = pos.get("value", "")
                if segment != expected:
                    warnings.append(
                        {
                            "position": pos["idx"],
                            "name": pos_name,
                            "expected": expected,
                            "got": segment,
                            "message": f"前缀不匹配: 期望 '{expected}', 得到 '{segment}'",
                        }
                    )
                result[pos_name] = segment
                continue

            # ----- 透传位 -----
            if pos_type == "passthrough":
                result[pos_name] = segment
                continue

            # ----- 枚举解码 -----
            values = pos.get("values", {})
            if segment in values:
                decoded_val = values[segment]
                if isinstance(decoded_val, dict):
                    # 主值: 优先 code (短代号, 便于程序处理)
                    # 补充: _zh, _en 作为展示用
                    result[pos_name] = decoded_val.get("code") or decoded_val.get("zh") or decoded_val
                    if "zh" in decoded_val:
                        result[f"{pos_name}_zh"] = decoded_val["zh"]
                    if "en" in decoded_val:
                        result[f"{pos_name}_en"] = decoded_val["en"]
                else:
                    result[pos_name] = decoded_val
                result[f"{pos_name}_raw"] = segment
            else:
                result[pos_name] = segment
                result[f"{pos_name}_raw"] = segment
                warnings.append(
                    {
                        "position": pos["idx"],
                        "name": pos_name,
                        "name_zh": pos.get("name_zh", ""),
                        "value": segment,
                        "message": f"值 '{segment}' 不在已知编码表中",
                    }
                )

        if cursor != len(raw):
            warnings.append(
                {
                    "position": -1,
                    "name": "trailing",
                    "message": f"解析后剩余 {len(raw) - cursor} 字符未消费: '{raw[cursor:]}'",
                }
            )

        # 按 display_separators 还原 display (优先), 降级走 group 字段
        separators = cfg["decoder"].get("display_separators")
        result["display"] = self.format_display(
            raw,
            cfg["decoder"]["positions"],
            separators=separators,
        )

        if warnings:
            result["_warnings"] = warnings

        return result

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def list_series(self) -> list[dict]:
        return [
            {
                "series": cfg["series"],
                "manufacturer": cfg.get("manufacturer", ""),
                "name": cfg.get("series_name_zh", ""),
                "prefix": cfg.get("router", {}).get("prefix", ""),
            }
            for cfg in self.loader.load_all()
        ]

    # ------------------------------------------------------------------
    # LLM 视图: 把 decode() 结果转成 Dify LLM 友好的文本行 (zh + en 双语)
    # ------------------------------------------------------------------
    def build_llm_view(self, result: dict) -> list[str]:
        """从 decode() 返回的 dict 构 llm_view 文本行 (Dify LLM 友好).

        复用 decode() 已算好的 display / _suffix / _warnings / 各 *_zh / *_en / code 字段.
        不修改 result (纯函数).

        Returns:
            list[str]: 文本行, 顺序固定 (header → 段 → warnings), 用 \\n join 即可拼 Dify prompt.
        """
        lines: list[str] = []
        # 按 result["series"] 取 cfg (沿用 decode() 加载路径, 不污染 ProductDecoder 状态)
        cfg = self.loader.load(result["series"])
        meta = cfg.get("metadata", {})

        # --- 头部 6 行 (code/厂商/系列 各 zh+en) ---
        # 完整型号: result.display (如果有) 或原 raw_input
        model_display = result.get("display") or result.get("raw_input") or ""
        full_code = model_display

        lines.append(f"完整型号: {full_code}")
        lines.append(f"Full order code: {full_code}")

        # 厂商: 优先 metadata.manufacturer 字典 (rich: {zh, en, code}), 降级用 cfg.manufacturer 字符串
        mfr_meta = meta.get("manufacturer")
        if isinstance(mfr_meta, dict) and mfr_meta:
            mfr_zh = mfr_meta.get("zh") or mfr_meta.get("code", "")
            mfr_en = mfr_meta.get("en") or mfr_meta.get("code", "")
        else:
            mfr_zh = mfr_en = cfg.get("manufacturer", "")
        lines.append(f"厂商: {mfr_zh}")
        lines.append(f"Manufacturer: {mfr_en}")

        # 系列: 优先 metadata.series 字典, 降级用 cfg.series_name_zh / _en
        series_meta = meta.get("series")
        if isinstance(series_meta, dict) and series_meta:
            series_zh = series_meta.get("zh") or series_meta.get("code", "")
            series_en = series_meta.get("en") or series_meta.get("code", "")
        else:
            series_zh = cfg.get("series_name_zh", "")
            series_en = cfg.get("series_name_en", "")
        lines.append(f"系列: {series_zh}")
        lines.append(f"Series: {series_en}")

        # _suffix 非空时头部第 7 行
        suffix = result.get("_suffix", "")
        if suffix:
            lines.append(f"后缀: {suffix}")

        # --- 第一个 --- 分隔 ---
        lines.append("---")

        # --- 段划分 + position 行 ---
        # 获取 display_separators, 跟 cfg positions 顺序对齐
        separators = cfg["decoder"].get("display_separators") or []
        display = result.get("display", "")

        # 段头: 用 display.split("-") 切; 段间用 '---' 分隔
        if display and separators:
            segments = display.split("-")
        else:
            # 降级: 无 display 或无 separators → 单一段, 不带 [段 X] 头
            segments = [display] if display else []

        # 累计 cursor 走 cfg positions, 算每个 position 落在哪段
        positions = cfg["decoder"]["positions"]
        # separators 是 display 字符串中的绝对位置 (如 [7, 12] 表示第 7 和第 12 字符后是 '-')
        # 按升序排, 直接作为段边界
        seg_boundaries: list[int] = sorted(separators)
        # 段内累计 char_count
        # 注: segments 为空时也建空 map, 下面的渲染循环会跳过 [段 X] 头
        seg_pos_map: dict[int, list[dict]] = {i: [] for i in range(len(segments))}
        cursor = 0
        for pos in positions:
            char_count = pos.get("char_count", len(str(result.get(pos["name"], ""))))
            pos_end = cursor + char_count
            # 找这个 position 落在哪个段 (cursor 到 pos_end 之间的段边界)
            seg_idx = 0
            for boundary in seg_boundaries:
                if pos_end > boundary:
                    seg_idx += 1
                else:
                    break
            # segments 为空 (无 display / 无 separators) → 全部塞进 seg 0
            if not segments:
                seg_idx = 0
            if seg_idx not in seg_pos_map:
                seg_pos_map[seg_idx] = []
            seg_pos_map[seg_idx].append(pos)
            cursor = pos_end

        # 渲染每段
        for seg_idx, seg_label in enumerate(segments):
            seg_positions = seg_pos_map.get(seg_idx, [])
            if not seg_positions and segments:
                # 段内 0 个 position → 不渲染 [段 X] 头 (避免空段)
                continue
            if segments:
                lines.append(f"[段 {seg_label}]")
            for pos in seg_positions:
                pos_name = pos["name"]
                # value 缺失 fallback: code 优先 (跟 decode() engine.py:133 一致)
                decoded = result.get(pos_name)
                if isinstance(decoded, dict):
                    val_zh = decoded.get("zh")
                    val_en = decoded.get("en")
                    val_code = decoded.get("code")
                else:
                    val_zh = None
                    val_en = None
                    val_code = decoded

                # 未知码: val 缺失 / 是 raw 字符串 (decode() 未知时存 raw)
                # 判定: 没 zh/en 且 val_code == raw_input
                raw_val = result.get(f"{pos_name}_raw")
                is_unknown = val_zh is None and val_en is None and (val_code is None or val_code == raw_val)
                if is_unknown:
                    val_zh = "?"
                    val_en = "?"

                # name 缺失 fallback: 走 cfg positions 的 name (英文 id)
                name_zh = pos.get("name_zh") or pos["name"]
                name_en = pos.get("name_en") or pos["name"]

                if val_zh == "?" and val_en == "?":
                    line = f"{name_zh}: ? / {name_en}: ?"
                else:
                    zh_part = val_zh if val_zh is not None else (val_code or "")
                    en_part = val_en if val_en is not None else (val_code or "")
                    line = f"{name_zh}: {zh_part} / {name_en}: {en_part}"
                lines.append(line)

            # 段间 --- (但只在还有下一段时)
            if seg_idx < len(segments) - 1 and seg_pos_map.get(seg_idx + 1):
                lines.append("---")

        # --- 尾部: warnings 段 ---
        warnings = result.get("_warnings", [])
        if warnings:
            lines.append("---")
            for w in warnings:
                # engine.py 现有格式: dict 含 message 字段, 或 str
                if isinstance(w, dict):
                    msg = w.get("message", str(w))
                else:
                    msg = str(w)
                lines.append(f"[WARN] {msg}")

        return lines

    @staticmethod
    def format_display(
        normalized: str,
        positions: list[dict],
        separators: list[int] | None = None,
    ) -> str:
        """还原 display 字符串 (标准化后无横线 → 加横线可读形式).

        优先级:
          1. cfg.decoder.display_separators (显式分隔位) — 真实厂商写法
          2. position.group 字段 (每个 position 一个 group 号, 跨 group 插横线)
          3. 都不存在: 降级, 直接返回 normalized

        示例 (display_separators=[7, 12]):
            "1LE00011AA421AA4" (16 字符) → "1LE0001-1AA42-1AA4"

        示例 (position.group = [1, 1, 2, 2, 2, 3, 4, 4, 4]):
            "1LE00011AA421AA4" → 按 group 累计字符数边界插 "-"
            → "1LE0001-1AA4-21-AA4"
        """
        # 1. 优先: 显式 display_separators
        if separators:
            # 在每个 separator 位置后插 "-"
            valid = sorted(b for b in separators if 0 < b < len(normalized))
            chars = list(normalized)
            for b in reversed(valid):
                chars.insert(b, "-")
            return "".join(chars)

        # 2. 降级: 按 position.group 字段
        if not any(pos.get("group") for pos in positions):
            return normalized

        # 计算每个 group 结束时的累计字符数 (取该 group 最后一次出现后的 cursor)
        group_boundaries: dict[int, int] = {}
        cursor = 0
        for pos in positions:
            cursor += pos.get("char_count", 1)
            g = pos.get("group")
            if g is not None:
                group_boundaries[g] = cursor

        # 在 group 边界 (除最后一个 group) 之后插 "-"
        max_g = max(group_boundaries)
        boundaries = sorted(pos for g, pos in group_boundaries.items() if pos < len(normalized) and g < max_g)
        chars = list(normalized)
        for b in reversed(boundaries):
            chars.insert(b, "-")
        return "".join(chars)
