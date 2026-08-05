#!/usr/bin/env python3
"""
Neighbors command for the MeshCore Bot
Triggers one zero-hop neighbor discovery cycle on demand
"""

import asyncio
from typing import Any, Optional

from ..models import MeshMessage
from .base_command import BaseCommand


class NeighborsCommand(BaseCommand):
    """Runs one neighbor discovery cycle immediately.

    The scheduled interval has a 12 hour floor (the firmware's band), which makes
    waiting for the scheduler impractical when testing or after moving the node.
    This is the bot's equivalent of the firmware's ``discover.neighbors``.

    A cycle takes at least ``neighbors_discover_window`` seconds — 60 by default —
    so this acknowledges immediately and reports the result in a second message
    rather than holding the reply open.
    """

    # Plugin metadata
    name = "neighbors"
    keywords = ['neighbors', 'neighbours']
    description = "Runs a zero-hop neighbor discovery cycle (DM only)"
    requires_dm = True
    cooldown_seconds = 900  # 15 minutes; a cycle costs airtime
    category = "special"

    def __init__(self, bot: Any):
        """Initialize the neighbors command.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self.command_enabled = self.get_config_value(
            'Neighbors_Command', 'enabled', fallback=True, value_type='bool'
        )
        # Tracked so a second invocation cannot start an overlapping cycle: two
        # concurrent discover rounds would collect into each other's window.
        self._cycle_task: Optional[asyncio.Task] = None

    def get_help_text(self) -> str:
        """Get help text for the neighbors command.

        Returns:
            str: The help text for this command.
        """
        return self.translate('commands.neighbors.description')

    def can_execute(self, message: MeshMessage, skip_channel_check: bool = False) -> bool:
        """Check if the neighbors command can be executed.

        Args:
            message: The message triggering the command.
            skip_channel_check: Passed through to the base implementation.

        Returns:
            bool: True if the command can be executed, False otherwise.
        """
        if not self.command_enabled:
            return False
        return super().can_execute(message, skip_channel_check=skip_channel_check)

    def _get_capture_service(self) -> Any:
        """The packet capture service instance, or None when unavailable."""
        service = getattr(self.bot, 'packet_capture_service', None)
        if service is not None:
            return service
        # The alias is set up at init; fall back to the service registry in case
        # the service was loaded but not aliased.
        services = getattr(self.bot, 'services', None) or {}
        try:
            return services.get('packetcapture')
        except AttributeError:
            return None

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the neighbors command.

        Args:
            message: The message triggering the command.

        Returns:
            bool: True if handled (including the error and busy notices).
        """
        service = self._get_capture_service()
        if service is None or not getattr(service, 'neighbors_enabled', False):
            await self.send_response(message, self.translate('commands.neighbors.disabled'))
            return True

        if self._cycle_task is not None and not self._cycle_task.done():
            await self.send_response(message, self.translate('commands.neighbors.busy'))
            return True

        cfg = service.neighbors_config
        self.logger.info(f"User {message.sender_id} requested a neighbors discovery cycle")
        await self.send_response(
            message,
            self.translate('commands.neighbors.started', seconds=int(cfg.discover_window)),
        )

        # Run detached so the discover window does not hold the command open, and
        # bound it so a stalled radio link cannot leave the task alive forever.
        self._cycle_task = asyncio.create_task(
            self._run_and_report(message, service, cfg.cycle_budget)
        )
        return True

    async def _run_and_report(self, message: MeshMessage, service: Any, budget: float) -> None:
        """Run one cycle and DM the outcome."""
        try:
            summary = await asyncio.wait_for(service.run_neighbors_cycle(), timeout=budget)
        except asyncio.TimeoutError:
            self.logger.error(f"Neighbors: manual cycle exceeded {budget:.0f}s and was abandoned")
            await self.send_response(
                message,
                self.translate('commands.neighbors.error',
                               error=f"timed out after {budget:.0f}s"),
                skip_user_rate_limit=True,
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Neighbors: manual cycle failed: {e}", exc_info=True)
            await self.send_response(
                message,
                self.translate('commands.neighbors.error', error=str(e)),
                skip_user_rate_limit=True,
            )
            return

        await self.send_response(
            message, self._format_summary(summary), skip_user_rate_limit=True
        )

    def _format_summary(self, summary: dict[str, Any]) -> str:
        """Render a cycle summary short enough for a mesh DM."""
        if not summary.get('ok'):
            reason = summary.get('reason') or 'unknown error'
            return self.translate('commands.neighbors.failed', reason=reason)

        found = summary.get('queried', 0)
        if not found:
            return self.translate('commands.neighbors.none')

        best = summary.get('best_snr')
        best_text = f"{best:.1f}dB" if isinstance(best, (int, float)) else "n/a"
        text = self.translate(
            'commands.neighbors.success',
            count=found,
            best_snr=best_text,
            recorded=summary.get('recorded', 0),
        )
        # Only mention brokers when at least one was actually tried, so an
        # operator with no MQTT does not see a confusing "0/0".
        if summary.get('attempted'):
            text += " " + self.translate(
                'commands.neighbors.published',
                succeeded=summary.get('succeeded', 0),
                attempted=summary.get('attempted', 0),
            )
        return text
