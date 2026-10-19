"""评估 CSV 模板生成

供 GET /api/evaluate/template 返回, 也供前端展示下载预览.
模板内容跟 spec "新建评估" 节里的示例 1:1 对齐, 用户改完即可上传.
"""

from __future__ import annotations

import csv
import io

# 示例题目来自西门子 1LE0 电机产品手册 (tests/fixtures/rag_eval/qa_dataset.yaml 同款)
_EXAMPLE_ROWS: list[tuple[str, str]] = [
    ("1LE0001-1AA4 是什么系列?", "西门子 1LE0 低压高效电机"),
    ("3RT2026 是接触器还是断路器?", "西门子 3RT 接触器系列"),
    ("请解释 1FK7 伺服电机的编码器类型", "1FK7 编码器类型取决于订货号后缀, 常见为增量式 TTL/HTL"),
]


def build_eval_template_csv() -> str:
    """生成模板 CSV 文本 (UTF-8, 含表头 + 示例)

    使用 csv.writer 确保格式正确:
    - 包含逗号的字段自动用双引号包裹
    - 双引号字段内的双引号正确转义

    Returns:
        多行字符串, 第一行表头, 后跟示例行
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["question", "ground_truth"])
    for q, gt in _EXAMPLE_ROWS:
        writer.writerow([q, gt])
    return output.getvalue()
