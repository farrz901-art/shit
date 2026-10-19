"""main.py argparse 解析测试

ingest 单文件支持 (2026-06-08):
- p_ingest 加 path 位置参数 (nargs="?")
"""

import os
from unittest.mock import patch


class TestIngestParser:
    """p_ingest 子解析器接受可选 path"""

    def test_ingest_accepts_no_args(self):
        """ingest 无参 → cmd_ingest 被调, path=None"""
        with patch("main.cmd_ingest") as mock_handler:
            with patch("sys.argv", ["main.py", "ingest"]):
                from main import main

                main()
            mock_handler.assert_called_once_with(path=None)

    def test_ingest_accepts_optional_path(self):
        """ingest ./abc.pdf → cmd_ingest 被调, path='./abc.pdf'"""
        with patch("main.cmd_ingest") as mock_handler:
            with patch("sys.argv", ["main.py", "ingest", "./abc.pdf"]):
                from main import main

                main()
            mock_handler.assert_called_once_with(path="./abc.pdf")

    def test_ingest_accepts_directory_path(self):
        """ingest ./pdfs/ → cmd_ingest 被调, path='./pdfs/'"""
        with patch("main.cmd_ingest") as mock_handler:
            with patch("sys.argv", ["main.py", "ingest", "./pdfs/"]):
                from main import main

                main()
            mock_handler.assert_called_once_with(path="./pdfs/")


class TestLoadDotenv:
    """main.py 启动时调 load_dotenv, 让 NEO4J_PASSWORD 等 .env.local 里的变量
    在 src.* 模块 import 时就生效 (create_app → Neo4jStore → 读 os.getenv).
    之前漏掉 → uvicorn 启动时 AuthError, 用户"明明配了 env" 却连不上."""

    def test_main_py_loads_dotenv_local_at_top_level(self):
        """main.py 源文件必须在所有 src.* import 之前 module-level 调
        load_dotenv(".env.local"). 这是约定; 真行为由 test_2 端到端验证."""
        from pathlib import Path

        main_path = Path(__file__).resolve().parent.parent / "main.py"
        source = main_path.read_text(encoding="utf-8")

        # 1. 必须 import load_dotenv
        assert "from dotenv import load_dotenv" in source, "main.py 缺 `from dotenv import load_dotenv`"

        # 2. 必须 module-level 调 load_dotenv(".env.local")
        load_idx = source.find('load_dotenv(".env.local")')
        assert load_idx > 0, 'main.py 缺 `load_dotenv(".env.local")` 调用'

        # 3. 必须在 `from src.core` 之前
        src_import_idx = source.find("from src.core")
        assert src_import_idx > load_idx, "load_dotenv 必须在 `from src.core` 之前 (顺序反了 Neo4jStore 拿不到 env)"

    def test_load_dotenv_actually_populates_environ(self, tmp_path):
        """端到端: 写临时 .env.local, subprocess 跑 load_dotenv 验真行为.
        不 import main (那条链路过重, 触 ezdxf 等无关依赖),
        只验 `load_dotenv('.env.local')` 本身能把文件内容灌进 os.environ."""
        import subprocess
        import sys

        env_file = tmp_path / ".env.local"
        env_file.write_text("LOAD_DOTENV_TEST_VAR=hello_from_dotenv", encoding="utf-8")

        env = {**os.environ, "PATH": "/usr/bin:/bin"}

        script = (
            "import os; "
            "from dotenv import load_dotenv; "
            "load_dotenv('.env.local'); "
            "print(os.environ.get('LOAD_DOTENV_TEST_VAR', ''))"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
            timeout=30,
        )
        assert "hello_from_dotenv" in result.stdout, (
            f"subprocess stdout 应含 'hello_from_dotenv', 实际: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
