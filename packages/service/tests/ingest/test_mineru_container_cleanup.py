"""MineruConverter._run_mineru 容器清理契约测试

修复前 bug: `remove=True` 只在 exit code 0 时清理容器。
           非 0 退出 / KeyboardInterrupt / 镜像缺失 → 容器残留。
修复后: 不管哪条路径走完，finally 必须 force remove 容器。

为什么需要单独测试这个？docker-py 的 `remove=True` 文档明确说
"the container will not be removed if it was not started properly
 or if the process was interrupted"。我们之前的实现太天真。
"""

import os
import shutil
import subprocess
from unittest.mock import MagicMock

import docker
import pytest

from src.ingest.pdf_processing.converters import MineruConverter


def _make_fake_client(run_returns=None, run_raises=None):
    """构造一个最小 fake docker client，containers.run 行为可注入。"""
    fake_container = MagicMock()
    fake_container.id = "fake-container-id"
    fake_container.wait.return_value = {"StatusCode": 0}
    fake_container.logs.return_value = b""
    fake_container.remove = MagicMock()

    fake_client = MagicMock()
    if run_raises is not None:
        fake_client.containers.run.side_effect = run_raises
    else:
        fake_client.containers.run.return_value = run_returns or fake_container
    return fake_client, fake_container


def _write_fake_pdf(tmp_path, name="sample.pdf") -> str:
    p = tmp_path / name
    p.write_bytes(b"%PDF-1.4\n%EOF\n")
    return str(p)


class TestRunMineruContainerCleanup:
    """_run_mineru 必须保证容器跑完一定被删（任何路径）"""

    def test_container_removed_on_normal_exit(self, tmp_path, monkeypatch):
        """正常退出 (exit 0)：容器必须被 force remove"""
        fake_client, fake_container = _make_fake_client()
        monkeypatch.setattr(docker, "from_env", lambda: fake_client)

        converter = MineruConverter()
        pdf_path = _write_fake_pdf(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        # 不抛异常 = 正常路径
        converter._run_mineru([pdf_path], str(out_dir))

        fake_container.remove.assert_called_with(force=True)

    def test_container_removed_on_container_error(self, tmp_path, monkeypatch):
        """容器非 0 退出 (ContainerError)：容器也必须被 force remove

        修复前 bug: remove=True 不会清理非 0 退出的容器。
        """
        fake_container = MagicMock()
        fake_container.id = "fake-container-id"
        fake_container.wait.return_value = {"StatusCode": 1}
        fake_container.logs.return_value = b"simulated mineru failure"
        fake_container.remove = MagicMock()

        fake_client = MagicMock()
        fake_client.containers.run.return_value = fake_container
        monkeypatch.setattr(docker, "from_env", lambda: fake_client)

        converter = MineruConverter()
        pdf_path = _write_fake_pdf(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with pytest.raises(MineruConverter.RunError) as exc_info:
            converter._run_mineru([pdf_path], str(out_dir))

        # 自定义异常带 exit_code 和 stderr 字段，调用方可以读
        assert exc_info.value.exit_code == 1
        assert exc_info.value.stderr == b"simulated mineru failure"

        # 关键断言：异常路径也要清理容器
        fake_container.remove.assert_called_with(force=True)

    def test_container_removed_on_keyboard_interrupt(self, tmp_path, monkeypatch):
        """KeyboardInterrupt (Ctrl-C / SIGINT)：容器也必须被 force remove

        修复前 bug: remove=True 不会清理被中断的容器。
        """
        fake_container = MagicMock()
        fake_container.id = "fake-container-id"
        fake_container.wait.side_effect = KeyboardInterrupt()
        fake_container.remove = MagicMock()

        fake_client = MagicMock()
        fake_client.containers.run.return_value = fake_container
        monkeypatch.setattr(docker, "from_env", lambda: fake_client)

        converter = MineruConverter()
        pdf_path = _write_fake_pdf(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with pytest.raises(KeyboardInterrupt):
            converter._run_mineru([pdf_path], str(out_dir))

        # 关键断言：中断路径也要清理容器
        fake_container.remove.assert_called_with(force=True)

    def test_remove_notfound_is_swallowed(self, tmp_path, monkeypatch):
        """容器已经被外部清理 (NotFound) 时，remove 不能再抛异常

        竞态：容器跑完外部/daemon 把它删了，finally 调用 remove(force=True)
        会抛 NotFound。这不能影响主流程的返回值。
        """
        fake_container = MagicMock()
        fake_container.id = "fake-container-id"
        fake_container.wait.return_value = {"StatusCode": 0}
        fake_container.remove.side_effect = docker.errors.NotFound("already gone")  # pyright: ignore[reportAttributeAccessIssue]

        fake_client = MagicMock()
        fake_client.containers.run.return_value = fake_container
        monkeypatch.setattr(docker, "from_env", lambda: fake_client)

        converter = MineruConverter()
        pdf_path = _write_fake_pdf(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        # 不应抛 NotFound
        converter._run_mineru([pdf_path], str(out_dir))

        fake_container.remove.assert_called_with(force=True)


# ---------------------------------------------------------------------------
# 真实 e2e：信 mock 原则——以上 4 个测试是代码逻辑契约验证，
# 下面这条是真实 docker 后端验证。
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="真实端到端测试较慢（跑真实 mineru 容器），设 RUN_SLOW_TESTS=1 开启",
)
def test_no_mineru_container_leaked_after_real_run(tmp_path):
    """真实 e2e：跑完 _run_mineru 后，docker ps -a 找不到任何 mineru 容器

    修复前 bug: remove=True 在非 0 退出时不会清容器 → docker ps -a 残留。
    修复后: 真实 mineru 跑完（成功 / 失败都算），`docker ps -a
            --filter ancestor=mineru:latest` 应为空。
    """
    real_pdf = "tests/fixtures/complex_pdf_test.pdf"  # (2026-06-29) 改用 fixtures
    if not os.path.exists(real_pdf):
        pytest.skip(f"真实测试 PDF 不存在: {real_pdf}")

    # 跑真实 mineru
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    pdf = input_dir / "sample.pdf"
    shutil.copy(real_pdf, pdf)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    converter = MineruConverter()
    converter._run_mineru([str(pdf)], str(out_dir))

    # 验证：docker ps -a 找不到任何 mineru:latest 容器残留
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "ancestor=mineru:latest",
            "--filter",
            "status=exited",
            "--format",
            "{{.ID}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    leaked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert not leaked, f"_run_mineru 跑完有 {len(leaked)} 个 mineru 容器残留: {leaked}\n完整 stdout: {result.stdout!r}"
