from types import SimpleNamespace

import pytest

from app import main
from app.services import ai_service


class FakeScheduler:
    def __init__(self):
        self.jobs = []
        self.started = False
        self.shutdown_called = False
        self.shutdown_wait = None

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append({"func": func, "trigger": trigger, **kwargs})

    def start(self):
        self.started = True

    def shutdown(self, wait=False):
        self.shutdown_called = True
        self.shutdown_wait = wait


@pytest.mark.asyncio
async def test_lifespan_skips_report_jobs_when_ai_report_generation_disabled(monkeypatch):
    scheduler = FakeScheduler()

    async def noop():
        return None

    monkeypatch.setattr(main, "AsyncIOScheduler", lambda: scheduler)
    monkeypatch.setattr(main, "prepare_database_on_startup", noop)
    monkeypatch.setattr(main, "update_prices_task", noop)
    monkeypatch.setattr(main, "update_news_task", noop)
    monkeypatch.setattr(main.settings, "ENABLE_MARKET_WARMUP", False)
    monkeypatch.setattr(main.settings, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(main.settings, "ENABLE_AI_REPORT_GENERATION", False)
    monkeypatch.setattr(main.settings, "ENABLE_NOTIFICATION_SCHEDULER", False)

    fake_app = SimpleNamespace(state=SimpleNamespace())

    async with main.lifespan(fake_app):
        job_ids = {job["id"] for job in scheduler.jobs}

        assert scheduler.started is True
        assert fake_app.state.scheduler is scheduler
        assert "update_prices_task" in job_ids
        assert "update_news_task" in job_ids
        assert "generate_daily_reports" not in job_ids
        assert "generate_daily_reports_startup" not in job_ids

    assert scheduler.shutdown_called is True
    assert scheduler.shutdown_wait is False


@pytest.mark.asyncio
async def test_generate_daily_reports_returns_before_session_when_disabled(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ENABLE_AI_REPORT_GENERATION", False)
    monkeypatch.setattr(
        ai_service,
        "AsyncSessionLocal",
        lambda: pytest.fail("AsyncSessionLocal should not be opened when AI report generation is disabled"),
    )

    await ai_service.generate_daily_reports()


@pytest.mark.asyncio
async def test_generate_report_for_ticker_blocks_when_disabled(monkeypatch):
    class UnexpectedDb:
        async def execute(self, query):
            _ = query
            pytest.fail("database should not be queried when AI report generation is disabled")

    monkeypatch.setattr(ai_service.settings, "ENABLE_AI_REPORT_GENERATION", False)

    with pytest.raises(RuntimeError, match="ENABLE_AI_REPORT_GENERATION"):
        await ai_service.generate_report_for_ticker("NVDA", UnexpectedDb())
