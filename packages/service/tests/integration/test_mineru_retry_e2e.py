"""mineru 失败重试 e2e 集成测试

复现 spec 里的实验 D 场景：1LE1.pdf (96 页) + 7 个小文件一起批处理 →
mineru 内部 batch 并发 → task#1 失败 → 走单独重试路径 → 8 个最终全成功。

跑一次约 5-8 分钟（mineru 模型加载 + 1LE1 处理两次 + 其它 7 个一次）。
默认不跑，需手动指定 marker：
    pytest tests/integration/test_mineru_retry_e2e.py -m slow
"""

from pathlib import Path

import pytest

from src.ingest.pdf_processing.converters import MineruConverter

pytestmark = [pytest.mark.slow, pytest.mark.integration]

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# 实验 D 复现：8 个文件（mineru 桶）
EXPERIMENT_D_FILES = [
    "1LE1.pdf",  # 96 页大文件，会被 mineru 拆 batch 独占
    "jpg_test.jpg",
    "png_test.png",
    "complex_pdf_test.pdf",
    "AI外贸智能体RAG方案.docx",
    "ppt_test.pptx",
    "excel_test.xlsx",
    "定制服务器05-26.pdf",
]


def _docker_daemon_alive() -> bool:
    """(2026-06-14) mineru 走 Docker, 缺 Docker daemon 时跳.

    检查: Windows named pipe `//./pipe/docker_engine` 是否存在; Linux `/var/run/docker.sock`.

    (2026-06-29) 改用 os.listdir 列举 named pipe 目录: pathlib.Path + os.path.exists
    都对 Windows named pipe 返 False (Path 不识别 named pipe 路径形式). os.listdir
    走 win32 FindFirstFile 列举真管道, 看到 docker_engine 名字即 daemon 启动.
    """
    import os
    import platform

    if platform.system() == "Windows":
        try:
            return "docker_engine" in os.listdir("//./pipe")
        except OSError:
            return False
    return Path("/var/run/docker.sock").exists()


def _mineru_image_available() -> bool:
    """(2026-07-08) Docker daemon 活着但拉不到 mineru:latest (沙箱无外网) 时也 skip.

    docker images 看本地有没有; 有就 true, 没有再尝试 docker pull (快速试, 失败返 False).
    避免 5-8 分钟跑下来发现 403 Forbidden 白等.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "mineru:latest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "mineru:latest" in result.stdout:
            return True
    except subprocess.TimeoutExpired, FileNotFoundError, OSError:
        return False

    # 本地没镜像, 试 pull (10s 超时, 网络不通快速返 False)
    try:
        result = subprocess.run(
            ["docker", "pull", "mineru:latest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired, FileNotFoundError, OSError:
        return False


@pytest.mark.slow
@pytest.mark.skipif(not _docker_daemon_alive(), reason="Docker daemon 不可用, 跳过 mineru e2e")
@pytest.mark.skipif(
    not _mineru_image_available(),
    reason="沙箱无 mineru:latest 镜像 (Docker Hub 拉不到, 403 Forbidden), 跳过 mineru e2e",
)
def test_mineru_retry_e2e_experiment_d(tmp_path):
    """实验 D：8 个文件批处理，1LE1 触发 mineru 内部并发失败 → 走单独重试 → 全成功"""
    # 准备：fixtures 里所有文件都存在
    pdf_paths = []
    for name in EXPERIMENT_D_FILES:
        src = FIXTURES / name
        assert src.exists(), f"fixture 缺失: {src}"
        pdf_paths.append(str(src))

    out_dir = tmp_path / "mineru_out"
    out_dir.mkdir()

    # 跑
    converter = MineruConverter()
    results = converter.convert_batch(pdf_paths, str(out_dir))

    # 断言：返回字典含全部 8 个文件
    assert len(results) == len(EXPERIMENT_D_FILES), f"results 应有 {len(EXPERIMENT_D_FILES)} 项，实际 {len(results)}"

    # 断言：每个文件都有非空、非 [ERROR] 开头的 md 内容
    failed = []
    for path, content in results.items():
        if not content or content.startswith("[ERROR]"):
            failed.append((Path(path).name, content[:200] if content else "<空>"))
    assert not failed, f"以下文件未成功: {failed}"

    # 断言：1LE1 内容长度像样（96 页文档，至少几万字符）
    le1_path = str(FIXTURES / "1LE1.pdf")
    assert len(results[le1_path]) > 50_000, f"1LE1.md 内容过短 ({len(results[le1_path])} 字符)，可能不完整"
