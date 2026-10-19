"""Mineru 转换器 - 适合复杂 PDF"""

import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from loguru import logger

from .base import Converter


class MineruConverter(Converter):
    """mineru转换器 - 适合复杂PDF"""

    name = "mineru"
    # PDF + 图片（OCR）+ Office 现代 OOXML 格式（mineru 验证通过）
    # .xls (BIFF8 旧格式) 不支持——mineru --help 明确只列 pdf, image, docx, pptx, xlsx
    # .xlsx (OOXML 新格式) 支持——真容器跑测试产出 <table> markdown
    extensions = [
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",  # 图片
        ".docx",
        ".pptx",
        ".xlsx",  # Office OOXML
    ]

    class RunError(Exception):
        """mineru 容器跑失败（非 0 退出 / 启动失败 / 中断等）

        不用 docker.errors.ContainerError 是因为：
        1. 它是 docker-py 的内部异常类型，我们不该把 docker 当成公开 API
        2. 让本模块不依赖 docker 的异常体系（convert_batch 就不必 import docker）
        """

        def __init__(self, exit_code: int, stderr: bytes):
            self.exit_code = exit_code
            self.stderr = stderr
            super().__init__(f"mineru 容器 exit {exit_code}")

    @staticmethod
    def can_handle(info) -> bool:
        """mineru 接收所有 PDFInfo

        简单/复杂 PDF 的分发在更上层做：
        - 简单 PDF（含文字）已被 KreuzbergConverter 截走（CONVERTERS 顺序在前）
        - mineru 实际处理的是：复杂 PDF + 非 PDF（图、Office）
        """
        return True

    @staticmethod
    def resolve_md_path(pdf_path: str, output_dir: str, method: str = "auto") -> str:
        """构造mineru生成的markdown文件路径

        mineru实际输出结构（已用真实容器验证）:
            <output_dir>/<pdf_stem>/<method>/<pdf_stem>.md

        注意：嵌套目录是 **PDF 文件名（stem）**，不是输入目录名。
        例如 /tmp/output/sample/auto/sample.md 中两个 sample 都是 PDF 文件名。
        """
        return os.path.join(
            os.path.abspath(output_dir),
            Path(pdf_path).stem,
            method,
            f"{Path(pdf_path).stem}.md",
        )

    def convert(self, pdf_path: str, output_path: str) -> str:
        """mineru不支持单文件直接处理，使用批量接口"""
        return self.convert_batch([pdf_path], os.path.dirname(output_path)).get(pdf_path, "")

    # mineru backend：默认pipeline（CPU 友好，无GPU也能跑）。
    # 真实运行验证：VLM/hybrid-* backend 需要 CUDA，无 GPU 时容器 exit 1 不产出任何文件。
    DEFAULT_BACKEND = "pipeline"

    def _run_mineru(self, pdf_paths: Sequence[str], output_dir: str) -> None:
        """跑一次 docker mineru 容器；失败抛 RunError。

        隔离输入目录 + 任何路径（exit 0 / 非 0 / 中断）都强制清理容器。
        不用 remove=True 是因为它只清理 exit 0 的容器。
        """
        # 重依赖 lazy: docker SDK 启动慢 (~300ms), 非 mineru 路径不需要
        import docker  # noqa: E402
        from docker.types import DeviceRequest  # noqa: E402

        client = docker.from_env()
        try:
            with tempfile.TemporaryDirectory(prefix="mineru_input_") as isolated_input:
                # 复制本批 PDF 到隔离目录
                # 用 shutil.copy 而不是 link：跨文件系统 link 容易失败，copy 更稳
                for pdf_path in pdf_paths:
                    shutil.copy(pdf_path, isolated_input)

                # 关键：必须显式请求 GPU 设备，否则容器内 CUDA 不可用
                # （docker-py SDK 默认不传 GPU，等价于 docker run 没加 --gpus all）
                gpu_request = DeviceRequest(count=-1, capabilities=[["gpu"]])
                container = client.containers.run(
                    "mineru:latest",
                    f"mineru -p /app/input -o /app/output -b {self.DEFAULT_BACKEND}",
                    volumes={
                        isolated_input: {"bind": "/app/input", "mode": "ro"},
                        output_dir: {"bind": "/app/output", "mode": "rw"},
                    },
                    device_requests=[gpu_request],
                    detach=True,
                )
                try:
                    result = container.wait()
                    if result["StatusCode"] != 0:
                        raise self.RunError(
                            result["StatusCode"],
                            container.logs(stdout=False, stderr=True),
                        )
                finally:
                    try:
                        container.remove(force=True)
                    except docker.errors.NotFound:  # pyright: ignore[reportAttributeAccessIssue]  # docker.errors 子模块在 stub 不全
                        pass
        finally:
            client.close()

    def convert_batch(self, pdf_paths: Sequence[str], output_dir: str) -> dict[str, str]:
        """mineru 批量处理：失败时按磁盘真相源分类，失败文件逐个单独重跑 1 次。

        流程：
        1. 跑一次 mineru 批处理（不管成功/失败都继续往下）
        2. 用 resolve_md_path 扫每个 pdf_path 在 output_dir 下的 md
           - 存在 → 加入 results
           - 不存在 → 加入 retry_targets
        3. retry_targets 非空时，逐个调 _run_mineru([single_file])
           - 重试成功 → 读盘加入 results
           - 重试仍失败 → results[path] = "[ERROR] ..."
        """
        if not pdf_paths:
            return {}

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 第 1 轮：批量跑（RunError 不让中断，磁盘真相源会兜住）
        try:
            self._run_mineru(pdf_paths, output_dir)
        except self.RunError as e:
            stderr = e.stderr.decode("utf-8", errors="replace")
            failed_hint = self._parse_failed_files(stderr)
            logger.warning(f"  [mineru] 批处理 exit {e.exit_code}，stderr 解析疑似失败: {failed_hint}")

        # 用磁盘真相源分类
        results: dict[str, str] = {}
        retry_targets: Sequence[str] = []
        for pdf_path in pdf_paths:
            md_path = self.resolve_md_path(pdf_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, encoding="utf-8") as f:
                    results[pdf_path] = f.read()
            else:
                content = self._find_md_in_subdirs(output_dir, Path(pdf_path).stem)
                if content:
                    results[pdf_path] = content
                else:
                    retry_targets.append(pdf_path)

        # 第 1 轮全成功 → 直接返回
        if not retry_targets:
            return results

        # 第 2 轮：失败文件逐个单独跑（单文件不会触发 mineru 内部 batch 并发）
        retry_names = [Path(p).name for p in retry_targets]
        logger.info(f"  [mineru] 第 1 轮缺 {len(retry_targets)} 个文件输出，单独重试: {retry_names}")

        for failed_path in retry_targets:
            try:
                self._run_mineru([failed_path], output_dir)
            except self.RunError as e:
                stderr = e.stderr.decode("utf-8", errors="replace")
                results[failed_path] = f"[ERROR] mineru 单独重试仍失败 (exit {e.exit_code}): {stderr[-500:]}"
                continue

            # 重试容器成功，读盘
            md_path = self.resolve_md_path(failed_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, encoding="utf-8") as f:
                    results[failed_path] = f.read()
            else:
                content = self._find_md_in_subdirs(output_dir, Path(failed_path).stem)
                results[failed_path] = content or "[ERROR] mineru 单独重试容器成功但无 md 输出"

        return results

    @staticmethod
    def _parse_failed_files(stderr: str) -> set[str]:
        """从 mineru stderr 解析失败的文件 stem（仅日志用，不作为重试决策依据）

        匹配格式：'- task#1 (1LE1): All connection attempts failed'

        Args:
            stderr: mineru 容器 stderr 文本

        Returns:
            失败的 stem 集合；无匹配返回空集合
        """
        pattern = re.compile(r"- task#\d+ \((.+?)\):")
        return set(pattern.findall(stderr))

    @staticmethod
    def _find_md_in_subdirs(output_dir: str, pdf_stem: str) -> str:
        """兜底：在output_dir的所有子目录中查找 <pdf_stem>.md"""
        target = f"{pdf_stem}.md"
        for root, _, files in os.walk(output_dir):
            if target in files:
                with open(os.path.join(root, target), encoding="utf-8") as f:
                    return f.read()
        return ""
