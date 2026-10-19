"""文件结构化主入口（PDF + CAD）

统一入口 process_files()：按扩展名分流
- *.pdf  → PDF 流水线（kreuzberg / mineru）
- *.dxf / *.dwg → CAD 流水线（EzdxfConverter）

process_path() (2026-06-08 新增)：单文件/单目录/默认三路分发入口
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

from src.config.settings import settings

from .analyzers.pdf import PDFAnalyzer
from .archive_handler import ArchiveError, ArchiveHandler
from .converters import CONVERTERS, get_converter
from .converters.cad import EzdxfConverter
from .markdown_passthrough import MarkdownPassthroughHandler


def process_path(path: str | None = None, output_dir: str | None = None) -> dict | None:
    """三路分发：单文件 / 单目录 / 默认 config

    Args:
        path: 单文件路径 / 目录路径 / None（None 时走 config.toml 默认 input_dir）
        output_dir: 产物输出目录。None 时用 config.toml [paths].output_dir。
                   upload API 用此参数让产物落独立工作区。
    """
    if path is None:
        # None → 走 config 默认目录 (output_dir 走 config)
        return process_files(output_dir=output_dir)

    p = Path(path)
    if not p.exists():
        logger.warning("路径不存在: {}", path)
        return None

    # 显式传 output_dir 时才挂到 process_files，None 时让 process_files 自己读 config fallback
    def _dir_call(input_dir: str):
        if output_dir is not None:
            return process_files(input_dir=input_dir, output_dir=output_dir)
        return process_files(input_dir=input_dir)

    if p.is_file():
        # zip 文件不在单文件模式处理（透传给 process_files 走 zip 解压流水线）
        if p.suffix.lower() == ".zip":
            return _dir_call(str(p))
        # 其他单文件 → 按扩展名路由
        return _process_single_file(str(p), output_dir=output_dir)

    # 目录（含 zip 路径）→ 走完整目录流水线
    return _dir_call(str(p))


def process_uri(input_prefix: str, output_prefix: str, store) -> dict:
    """(2026-06-16) URI 模式入口: 把 inputs 借出到本地, 跑 process_files, outputs 回传.

    Args:
        input_prefix: 's3://rag-ingest/inputs/abc/input/' 或 'local://inputs/abc/input/'
        output_prefix: 's3://rag-ingest/inputs/abc/output/' 或 'local://inputs/abc/output/'
        store: ObjectStore 单例

    Returns:
        process_files() 返回的 dict
    """
    with tempfile.TemporaryDirectory(prefix="ingest_uri_") as local_root:
        local_input = Path(local_root) / "input"
        local_output = Path(local_root) / "output"
        local_input.mkdir(parents=True)
        local_output.mkdir(parents=True)

        # 1. 借 inputs 到本地
        for meta in store.list_prefix(input_prefix):
            with store.open_local_ctx(meta.uri) as lp:
                dst = local_input / Path(meta.uri).name
                shutil.copy(lp, dst)

        # 2. 跑旧 pipeline (本地模式, 0 改动)
        result = process_files(input_dir=str(local_input), output_dir=str(local_output))

        # 3. 把 outputs 回传到 ABC
        for p in Path(local_output).rglob("*"):
            if p.is_file():
                rel = p.relative_to(local_output)
                uri = f"{output_prefix.rstrip('/')}/{str(rel).replace(chr(92), '/')}"
                store.put_file(uri, str(p))

        return result or {}


def _process_single_file(file_path: str, output_dir: str | None = None) -> dict:
    """单文件模式：按扩展名路由到 document/cad/passthrough

    zip 文件不在这里处理（外层 process_path 把 zip 当目录透传）

    Args:
        file_path: 单文件绝对路径
        output_dir: 产物输出目录。None 时用 [paths].output_dir
    """
    # EzdxfConverter / MarkdownPassthroughHandler / settings 已在模块顶部 import
    p = Path(file_path)
    ext = p.suffix.lower()
    output_path = output_dir if output_dir else str(settings.paths.output_dir)

    if ext in MarkdownPassthroughHandler.extensions:
        return process_passthrough([file_path], output_path)
    if ext in EzdxfConverter.extensions:
        return process_cad_files([file_path], output_path)
    if any(ext in c.extensions for c in CONVERTERS.values()):
        return process_documents([file_path], output_path)

    # 未知扩展名
    logger.warning("不支持的文件格式: {}（跳过: {}）", ext, p.name)
    return {"document": [], "cad": [], "passthrough": []}


def process_files(input_dir: str | None = None, output_dir: str | None = None):
    """统一入口：按扩展名分 4 桶（Document / Markdown / CAD / Unknown）

    流程:
        1. 顶层 tempfile.TemporaryDirectory 隔离整批处理
        2. 递归扫 input_dir 所有文件
        3. 找 .zip 压缩包，逐个解压到 <temp_root>/<archive_stem>/
        4. 收集"待处理文件池" = 非压缩包原始文件 + 解压产物
        5. 按扩展名分 4 桶
        6. 各自走 process_documents / process_cad_files / process_passthrough
        7. 临时目录自动清理

    Args:
        input_dir:  输入目录，传 None 则从 config.toml 读 [paths].input_dir
        output_dir: 输出目录，传 None 则从 config.toml 读 [paths].output_dir
    """
    # 重依赖 lazy: converters 注册表按需加载, 各 converter 是重依赖
    from .converters import CONVERTERS  # noqa: E402

    paths = settings.paths
    input_path = Path(input_dir) if input_dir else paths.input_dir
    output_path = Path(output_dir) if output_dir else paths.output_dir
    archive_cfg = settings.archive_config

    if not input_path.exists():
        logger.warning("输入目录不存在: {}", input_path)
        return None

    with tempfile.TemporaryDirectory(prefix="rag_ingest_") as temp_root:
        temp_path = Path(temp_root)
        archive_handler = ArchiveHandler(
            max_depth=archive_cfg.max_depth,
            max_total_size=archive_cfg.max_total_size,
            max_file_count=archive_cfg.max_file_count,
        )

        # 1. 递归扫所有原始文件
        all_files = [f for f in input_path.rglob("*") if f.is_file()]

        # 2. 找 .zip 压缩包并解压
        archives = [f for f in all_files if archive_handler.is_supported(f)]
        for archive in archives:
            try:
                archive_handler.extract(archive, temp_path)
            except ArchiveError as e:
                logger.warning("压缩包解压失败，跳过 {}: {}", archive.name, e)

        # 3. 收集"待处理文件池" = 非压缩包原始文件 + 解压产物
        pool = [f for f in all_files if not archive_handler.is_supported(f)]
        for extracted in temp_path.rglob("*"):
            if extracted.is_file():
                pool.append(extracted)

        # 4. 按扩展名分桶
        document_converters = list(CONVERTERS.values())  # kreuzberg + mineru
        cad_converters = [EzdxfConverter]

        buckets = {"document": [], "passthrough": [], "cad": [], "unknown": []}
        for f in pool:
            ext = f.suffix.lower()
            if ext in MarkdownPassthroughHandler.extensions:
                buckets["passthrough"].append(f)
            elif any(ext in c.extensions for c in cad_converters):
                buckets["cad"].append(f)
            elif any(ext in c.extensions for c in document_converters):
                buckets["document"].append(f)
            else:
                buckets["unknown"].append(f)

        logger.info(
            "扫描到 {} 个文档 + {} 个 CAD + {} 个 md 直通",
            len(buckets["document"]),
            len(buckets["cad"]),
            len(buckets["passthrough"]),
        )
        if buckets["unknown"]:
            logger.warning("{} 个未知格式将被跳过", len(buckets["unknown"]))

        # 5. 警告 unknown
        for f in buckets["unknown"]:
            try:
                rel = f.relative_to(input_path)
            except ValueError:
                rel = f
            logger.warning("不支持的格式，跳过: {}", rel)

        results: dict[str, Any] = {"document": None, "cad": None, "passthrough": None}

        # 6. 各自走各自流水线
        if buckets["passthrough"]:
            logger.info("=" * 50)
            logger.info("Markdown 直通")
            logger.info("=" * 50)
            results["passthrough"] = process_passthrough(
                [str(f) for f in buckets["passthrough"]],
                str(output_path),
            )

        if buckets["cad"]:
            logger.info("=" * 50)
            logger.info("CAD 流水线")
            logger.info("=" * 50)
            results["cad"] = process_cad_files(
                [str(f) for f in buckets["cad"]],
                str(output_path),
            )

        if buckets["document"]:
            logger.info("=" * 50)
            logger.info("Document 流水线")
            logger.info("=" * 50)
            results["document"] = process_documents(
                [str(f) for f in buckets["document"]],
                str(output_path),
            )

        if not any(buckets.values()):
            logger.warning("未找到可处理的文件")

        return results
    # 临时目录自动清理


def process_documents(
    file_paths: list[str],
    output_dir: str | None = None,
):
    """处理文档类文件（PDF / 图片 / Office / HTML / ...）

    Args:
        file_paths: 必传，显式传入要处理的文件列表
        output_dir: 输出目录，传 None 则用 [paths].output_dir
    """
    paths = settings.paths
    output_path = Path(output_dir) if output_dir else paths.output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("扫描到 {} 个文档文件", len(file_paths))

    if not file_paths:
        return {"processed": [], "errors": []}

    # 1. 一次性分析全部
    logger.info("=" * 50)
    logger.info("分析文档复杂度")
    logger.info("=" * 50)
    analyzer = PDFAnalyzer()
    infos = analyzer.analyze_all(file_paths)

    # 2. 分类
    # 重依赖 lazy: converters 注册表按需加载, 各 converter 是重依赖
    from .converters import CONVERTERS, classify_files  # noqa: E402

    converters = list(CONVERTERS.values())  # ezdxf 走自己的 process_cad_files，不在这
    grouped = classify_files(infos, converters)
    counts_line = " | ".join(f"{n}: {len(p)} 个" for n, p in grouped.items() if p)
    if counts_line:
        logger.info(counts_line)

    # 3. 打印每个文件的分析结果
    for file_path, info in infos.items():
        status = "简单" if info.is_simple else "复杂"
        logger.info("{}", Path(file_path).name)
        logger.info(
            "  类型: {} | 页数: {} | 文字: {} | 图片: {}", status, info.page_count, info.has_text, info.image_count
        )
        if info.reasons:
            logger.info("  原因: {}", ", ".join(info.reasons))

    # 4. 分组批量处理
    logger.info("=" * 50)
    logger.info("开始批量转换")
    logger.info("=" * 50)

    results = {"processed": [], "errors": []}

    for converter_name, paths_in_group in grouped.items():
        if not paths_in_group:
            continue

        logger.info("使用 {} 处理 {} 个文件", converter_name, len(paths_in_group))
        converter = get_converter(converter_name)

        try:
            batch_results = converter.convert_batch(paths_in_group, str(output_path))
            for file_path, content in batch_results.items():
                if content and not content.startswith("[ERROR]"):
                    results["processed"].append(
                        {
                            "file": Path(file_path).name,
                            "converter": converter_name,
                            "size": len(content),
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "file": Path(file_path).name,
                            "converter": converter_name,
                            "error": content or "内容为空",
                        }
                    )
                    logger.error("{}", Path(file_path).name)
        except Exception as e:
            for file_path in paths_in_group:
                results["errors"].append(
                    {
                        "file": Path(file_path).name,
                        "converter": converter_name,
                        "error": str(e),
                    }
                )
            logger.opt(exception=True).error("{} 批量处理失败: {}", converter_name, e)

    logger.info("=" * 50)
    logger.info("处理完成")
    logger.info("=" * 50)
    logger.info("成功: {} | 失败: {}", len(results["processed"]), len(results["errors"]))
    return results


def process_cad_files(
    file_paths: list[str],
    output_dir: str | None = None,
):
    """处理 CAD 文件（DWG/DXF）

    流程:
        1. 收 file_paths 列表
        2. 用 EzdxfConverter 逐个 convert
        3. 汇总成功/失败

    Args:
        file_paths: CAD 文件路径列表（必传，不再接受 str 目录隐式 glob）
        output_dir: CAD 输出目录，传 None 则用 [paths].output_dir
    """
    paths = settings.paths
    output_path = Path(output_dir) if output_dir else paths.output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    cad_paths = list(file_paths)
    logger.info("扫描到 {} 个 CAD 文件", len(cad_paths))

    if not cad_paths:
        return {"processed": [], "errors": []}

    converter = EzdxfConverter()

    logger.info("=" * 50)
    logger.info("开始 CAD 转换")
    logger.info("=" * 50)

    results = {"processed": [], "errors": []}

    for cad_path in cad_paths:
        logger.info("处理 {}", Path(cad_path).name)
        try:
            result = converter.convert(cad_path, str(output_path))
            results["processed"].append(
                {
                    "file": Path(cad_path).name,
                    "size": len(result["content"]),
                    "svg_count": len(result["svg_files"]),
                }
            )
            logger.info("产出 {} 张 SVG + {} 字 markdown", len(result["svg_files"]), len(result["content"]))
        except Exception as e:
            results["errors"].append(
                {
                    "file": Path(cad_path).name,
                    "error": str(e),
                }
            )
            logger.error("{}", e)

    logger.info("=" * 50)
    logger.info("CAD 处理完成")
    logger.info("=" * 50)
    logger.info("成功: {} | 失败: {}", len(results["processed"]), len(results["errors"]))
    if results["errors"]:
        logger.error("失败文件:")
        for item in results["errors"]:
            logger.error("  - {}: {}", item["file"], item["error"])

    return results


def process_passthrough(file_paths: list[str], output_dir: str | None = None) -> dict:
    """处理 .md 直通文件列表

    Args:
        file_paths: .md 文件路径列表
        output_dir: 输出目录，传 None 则用 [paths].output_dir

    Returns:
        {"processed": [...], "errors": [...]}
    """
    paths = settings.paths
    output_path = Path(output_dir) if output_dir else paths.output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    if not file_paths:
        return {"processed": [], "errors": []}

    handler = MarkdownPassthroughHandler()
    logger.info("扫描到 {} 个 md 直通文件", len(file_paths))

    results = {"processed": [], "errors": []}
    for file_path in file_paths:
        logger.info("复制 {}", Path(file_path).name)
        try:
            dst = handler.convert(file_path, str(output_path))
            results["processed"].append({"file": Path(file_path).name, "dst": dst})
            logger.info("已复制 -> {}", Path(dst).relative_to(output_path))
        except Exception as e:
            results["errors"].append({"file": Path(file_path).name, "error": str(e)})
            logger.error("{}", e)

    logger.info("=" * 50)
    logger.info("Markdown 直通处理完成")
    logger.info("=" * 50)
    logger.info("成功: {} | 失败: {}", len(results["processed"]), len(results["errors"]))
    return results


if __name__ == "__main__":
    process_files()
