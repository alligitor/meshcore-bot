"""Tests for the neighbors command (modules/commands/neighbors_command.py)."""

from __future__ import annotations

import asyncio
import types

import pytest

from modules.commands.neighbors_command import NeighborsCommand
from tests.conftest import mock_message


def make_service(*, neighbors_enabled=True, summary=None, hang=False,
                 raises=None, cycle_budget=5.0):
    """A stand-in for PacketCaptureService's neighbors surface."""
    service = types.SimpleNamespace()
    service.neighbors_enabled = neighbors_enabled
    service.neighbors_config = types.SimpleNamespace(
        discover_window=60.0, cycle_budget=cycle_budget
    )
    service.calls = 0

    async def run_cycle():
        service.calls += 1
        if hang:
            await asyncio.sleep(30)
        if raises is not None:
            raise raises
        return summary or {"ok": True, "queried": 0, "recorded": 0, "attempted": 0}

    service.run_neighbors_cycle = run_cycle
    return service


def make_command(command_mock_bot, service, *, enabled=True):
    """Build the command without __init__ (which reads config and the ACL)."""
    command_mock_bot.packet_capture_service = service
    command = object.__new__(NeighborsCommand)
    command.bot = command_mock_bot
    command.logger = command_mock_bot.logger
    command.command_enabled = enabled
    command._cycle_task = None

    sent: list[str] = []

    async def send_response(message, content, **kwargs):
        sent.append(content)
        return True

    command.send_response = send_response
    command.translate = lambda key, **kwargs: (
        key.split(".")[-1] + (" " + " ".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                              if kwargs else "")
    )
    return command, sent


@pytest.fixture
def message():
    return mock_message(content="neighbors", is_dm=True, sender_id="TestUser")


def test_command_metadata():
    # A cycle spends airtime and takes a minute, so it is DM-only with a cooldown.
    assert NeighborsCommand.requires_dm is True
    assert NeighborsCommand.cooldown_seconds == 900
    assert "neighbours" in NeighborsCommand.keywords


async def test_reports_when_discovery_is_disabled(command_mock_bot, message):
    command, sent = make_command(command_mock_bot, make_service(neighbors_enabled=False))
    assert await command.execute(message) is True
    assert sent == ["disabled"]


async def test_reports_when_the_service_is_absent(command_mock_bot, message):
    command, sent = make_command(command_mock_bot, None)
    command_mock_bot.services = {}
    assert await command.execute(message) is True
    assert sent == ["disabled"]


async def test_acknowledges_before_running_the_cycle(command_mock_bot, message):
    """The listen window is ~60s, far too long to hold the reply open."""
    service = make_service(summary={"ok": True, "queried": 2, "best_snr": 8.0,
                                    "recorded": 2, "attempted": 0})
    command, sent = make_command(command_mock_bot, service)

    assert await command.execute(message) is True
    assert sent == ["started seconds=60"]
    assert service.calls == 0  # not awaited inline

    await command._cycle_task
    assert len(sent) == 2
    assert sent[1].startswith("success")


async def test_summary_reports_count_snr_and_records(command_mock_bot, message):
    service = make_service(summary={"ok": True, "queried": 3, "best_snr": 8.25,
                                    "recorded": 3, "attempted": 0})
    command, sent = make_command(command_mock_bot, service)
    await command.execute(message)
    await command._cycle_task
    assert "count=3" in sent[1]
    assert "recorded=3" in sent[1]
    assert "best_snr=8.2dB" in sent[1]


async def test_summary_mentions_brokers_only_when_one_was_tried(command_mock_bot, message):
    """A operator with no MQTT should not be shown a confusing 0/0."""
    without = make_service(summary={"ok": True, "queried": 1, "best_snr": 1.0,
                                    "recorded": 1, "attempted": 0})
    command, sent = make_command(command_mock_bot, without)
    await command.execute(message)
    await command._cycle_task
    assert "published" not in sent[1]

    with_broker = make_service(summary={"ok": True, "queried": 1, "best_snr": 1.0,
                                        "recorded": 1, "attempted": 2, "succeeded": 1})
    command2, sent2 = make_command(command_mock_bot, with_broker)
    await command2.execute(message)
    await command2._cycle_task
    assert "published" in sent2[1]
    assert "succeeded=1" in sent2[1]
    assert "attempted=2" in sent2[1]


async def test_reports_when_nothing_answered(command_mock_bot, message):
    service = make_service(summary={"ok": True, "queried": 0, "recorded": 0, "attempted": 0})
    command, sent = make_command(command_mock_bot, service)
    await command.execute(message)
    await command._cycle_task
    assert sent[1] == "none"


async def test_reports_the_reason_a_cycle_did_not_run(command_mock_bot, message):
    service = make_service(summary={"ok": False, "reason": "radio not connected"})
    command, sent = make_command(command_mock_bot, service)
    await command.execute(message)
    await command._cycle_task
    assert sent[1] == "failed reason=radio not connected"


async def test_missing_snr_does_not_break_the_summary(command_mock_bot, message):
    service = make_service(summary={"ok": True, "queried": 1, "best_snr": None,
                                    "recorded": 1, "attempted": 0})
    command, sent = make_command(command_mock_bot, service)
    await command.execute(message)
    await command._cycle_task
    assert "best_snr=n/a" in sent[1]


async def test_cycle_errors_are_reported(command_mock_bot, message):
    service = make_service(raises=RuntimeError("radio exploded"))
    command, sent = make_command(command_mock_bot, service)
    await command.execute(message)
    await command._cycle_task
    assert sent[1].startswith("error")
    assert "radio exploded" in sent[1]


async def test_a_stalled_cycle_is_abandoned(command_mock_bot, message):
    service = make_service(hang=True, cycle_budget=0.05)
    command, sent = make_command(command_mock_bot, service)
    await command.execute(message)
    await command._cycle_task
    assert sent[1].startswith("error")
    assert "timed out" in sent[1]


async def test_a_second_request_will_not_overlap_the_first(command_mock_bot, message):
    """Two concurrent discover rounds would collect into each other's window."""
    service = make_service(hang=True, cycle_budget=5.0)
    command, sent = make_command(command_mock_bot, service)

    await command.execute(message)
    await command.execute(message)
    assert sent == ["started seconds=60", "busy"]

    command._cycle_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await command._cycle_task


async def test_a_finished_cycle_does_not_block_the_next_request(command_mock_bot, message):
    service = make_service(summary={"ok": True, "queried": 0, "recorded": 0, "attempted": 0})
    command, sent = make_command(command_mock_bot, service)

    await command.execute(message)
    await command._cycle_task
    await command.execute(message)
    await command._cycle_task

    assert service.calls == 2
    assert "busy" not in sent


def test_disabled_command_cannot_execute(command_mock_bot, message):
    command, _ = make_command(command_mock_bot, make_service(), enabled=False)
    assert command.can_execute(message) is False
