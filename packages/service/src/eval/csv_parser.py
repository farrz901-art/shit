"""CSV 评估集解析: 校验 + 清洗

设计目标: 拒绝一切 schema/编码/大小不合规, 失败给出可读中文错.
供 FastAPI multipart 上传和 scripts 都用.
"""

from __future__ import annotations

import csv
import io

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MIN_ROWS = 1
MAX_ROWS = 200


class CSVParsingError(ValueError):
    """CSV 校验失败, 抛出时带可读中文 message"""


def parse_eval_csv(content: bytes, filename: str = "<upload>") -> list[dict]:
    """解析评估集 CSV, 返回 [{question, ground_truth}, ...]

    Args:
        content: 文件原始字节
        filename: 仅用于错误信息 (不读盘)

    Returns:
        list[dict], 每条必须有 question 键, ground_truth 可为 None

    Raises:
        CSVParsingError: 任何 schema/编码/大小不合规
    """
    # 1. 文件大小
    if len(content) > MAX_FILE_SIZE:
        raise CSVParsingError(f"文件 {filename} 超过 5MB (实际 {len(content) // 1024}KB), 请精简数据")

    # 2. 编码 (UTF-8 strict)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CSVParsingError(f"文件 {filename} 不是 UTF-8 编码 ({e.reason}). 请用 Excel 另存为 CSV UTF-8") from e

    # 3. 解析 + 校验
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "question" not in reader.fieldnames:
        raise CSVParsingError(f"文件 {filename} 缺 'question' 列. 必须有表头: question,ground_truth")

    rows: list[dict] = []
    for line_no, raw in enumerate(reader, start=2):  # 第 1 行是表头
        q = (raw.get("question") or "").strip()
        gt = (raw.get("ground_truth") or "").strip() or None
        if not q:
            raise CSVParsingError(f"文件 {filename} 第 {line_no} 行 question 为空")
        rows.append({"question": q, "ground_truth": gt})

    # 4. 行数
    if len(rows) < MIN_ROWS:
        raise CSVParsingError(f"文件 {filename} 只有表头, 至少需要 {MIN_ROWS} 行数据")
    if len(rows) > MAX_ROWS:
        raise CSVParsingError(f"文件 {filename} 有 {len(rows)} 行, 最多 {MAX_ROWS} 行")

    return rows
