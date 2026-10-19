"""tests/ingest 子目录 conftest

ingest pipeline 改用 loguru 后 (2026-06-17 logging spec), 默认 sink 是 stderr 且
带格式前缀, pytest 的 capsys 抓不到. 这里用 loguru 官方推荐的 PropagateHandler
把 loguru 输出转到 stdlib logging, 让 pytest 的 caplog 抓到.

测试用 `caplog.text` / `[r.message for r in caplog.records]` 断言,
而不是 `capsys.readouterr().out`.

不影响业务行为, 测试结束 sink 自动 remove.

参考: https://loguru.readthedocs.io/en/stable/resources/migration.html#replacing-caplog-fixture-from-pytest-library
"""

from __future__ import annotations

import logging

import pytest
from loguru import logger


class PropagateHandler(logging.Handler):
    """把 loguru 日志 forward 到 stdlib root logger, 让 caplog 可见."""

    def emit(self, record: logging.LogRecord) -> None:
        # caplog 接 root logger 的 records
        logging.getLogger(record.name).handle(record)


@pytest.fixture(autouse=True)
def _ingest_loguru_to_stdlib(caplog: pytest.LogCaptureFixture):
    """autouse: 把 loguru sink 接到 stdlib logging, 让 caplog 抓 logger.warning().

    caplog 默认 level 是 WARNING, 测试需要 DEBUG/INFO 时显式 caplog.set_level("DEBUG").
    """
    handler_id = logger.add(PropagateHandler(), format="{message}", level="DEBUG")
    caplog.set_level(logging.DEBUG)
    yield
    logger.remove(handler_id)
