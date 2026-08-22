"""
trades/management/commands/run_auto_agent.py

Runs the autonomous trading bot for all active users.

USAGE:
  python manage.py run_auto_agent
  python manage.py run_auto_agent --interval 15
"""

import time
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run autonomous trading bot for all active users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=15,
            help='Minutes between each scan cycle (default: 15)'
        )

    def handle(self, *args, **options):
        interval_minutes = options['interval']
        interval_seconds = interval_minutes * 60

        self.stdout.write(self.style.SUCCESS(
            f'\n🤖 Auto Trading Bot Started!\n'
            f'   Scanning every {interval_minutes} minutes\n'
            f'   Press Ctrl+C to stop\n'
        ))

        cycle = 0

        while True:
            cycle += 1
            self.stdout.write(f'\n--- Bot Cycle #{cycle} ---')

            try:
                from trades.models import AgentConfig
                from trades.auto_agent import run_agent_cycle

                active_configs = AgentConfig.objects.filter(
                    is_active=True
                ).select_related('user')

                if not active_configs.exists():
                    self.stdout.write(
                        '  No active bots. Go to /trades/bot/ and click Start Bot.'
                    )
                else:
                    for config in active_configs:
                        self.stdout.write(
                            f'  Running bot for: {config.user.username}'
                        )
                        try:
                            run_agent_cycle(config.user)
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'  Error: {e}')
                            )

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n🛑 Stopped.'))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Error: {e}'))
                logger.exception("Auto agent error")

            try:
                self.stdout.write(
                    f'  Next scan in {interval_minutes} min...'
                )
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n🛑 Stopped.'))
                break