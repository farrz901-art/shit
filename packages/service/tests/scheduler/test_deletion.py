"""scheduler/deletion.py 单元测试 (mode 1, mock scheduler)"""

from unittest.mock import MagicMock

from src.scheduler.deletion import register_chat_jobs, register_deletion_jobs


def test_register_deletion_jobs_adds_job():
    scheduler = MagicMock()
    register_deletion_jobs(scheduler)
    scheduler.add_job.assert_called_once()


def test_register_chat_jobs_adds_job():
    scheduler = MagicMock()
    register_chat_jobs(scheduler)
    scheduler.add_job.assert_called_once()
