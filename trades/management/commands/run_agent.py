"""
trades/management/commands/run_agent.py

Django management command that runs the trading agent in the background.

Usage:
    python manage.py run_agent
    python manage.py run_agent --interval 10   (check every 10 seconds)

This is the "brain" of the system — it runs in a loop and automatically
monitors all open trades, closing them when TP or SL is hit.
"""

import time
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the AI trading agent that monitors open trades and closes them automatically.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='How many seconds to wait between each price check (default: 5)'
        )

    def handle(self, *args, **options):
        interval = options['interval']

        self.stdout.write(self.style.SUCCESS(
            f'\n🤖 AI Trading Agent started! Checking prices every {interval} seconds.\n'
            f'   Press Ctrl+C to stop.\n'
        ))

        cycle = 0

        while True:
            cycle += 1
            self.stdout.write(f'\n--- Cycle #{cycle} ---')

            try:
                # Run one monitoring cycle
                from trades.trade_monitor import check_and_close_trades
                from trades.price_service import get_live_price
                from trades.trade_monitor import update_price_history

                summary = check_and_close_trades()

                self.stdout.write(
                    f'  ✓ Checked: {summary["checked"]} trades | '
                    f'Errors: {summary["errors"]}'
                )

                # Show current prices for common symbols
                for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
                    price = get_live_price(symbol)
                    if price:
                        update_price_history(symbol, price)
                        self.stdout.write(f'  📈 {symbol}: ${price:,.2f}')

            except KeyboardInterrupt:
                # User pressed Ctrl+C — stop gracefully
                self.stdout.write(self.style.WARNING('\n\n🛑 Agent stopped by user.'))
                break

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Error in cycle: {e}'))
                logger.exception("Unexpected error in trading agent cycle")

            # Wait before next cycle
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n\n🛑 Agent stopped by user.'))
                break
