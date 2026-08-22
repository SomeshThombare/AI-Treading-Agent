"""
trades/management/commands/train_models.py

Django management command to train LSTM models.

USAGE:
  # Train ALL symbols
  python manage.py train_models

  # Train ONE specific symbol
  python manage.py train_models --symbol BTCUSDT
  python manage.py train_models --symbol EURUSD
  python manage.py train_models --symbol XAUUSD

  # Train with more candles for better accuracy
  python manage.py train_models --candles 2000

  # Train specific symbol with more candles
  python manage.py train_models --symbol BTCUSDT --candles 2000

SCHEDULE DAILY RETRAINING (Windows Task Scheduler):
  1. Open Task Scheduler
  2. Create Basic Task
  3. Set trigger: Daily at midnight
  4. Set action: python manage.py train_models
  5. Save task

This keeps models fresh with latest market data every day.
"""

import time
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Train LSTM models for price prediction. '
        'Run daily for best accuracy.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            default=None,
            help='Train specific symbol only (e.g. BTCUSDT, EURUSD, XAUUSD)'
        )
        parser.add_argument(
            '--candles',
            type=int,
            default=1000,
            help='Number of historical candles to use (default: 1000)'
        )

    def handle(self, *args, **options):
        symbol  = options.get('symbol')
        candles = options.get('candles', 1000)

        self.stdout.write(self.style.SUCCESS(
            '\n🤖 AI Trading Agent — Model Trainer\n'
            f'   Candles per symbol: {candles}\n'
        ))

        # Import here to avoid loading TensorFlow on startup
        from trades.ml.trainer import (
            train_symbol, train_all_symbols,
            CRYPTO_SYMBOLS, MT5_SYMBOLS
        )

        start_time = time.time()

        if symbol:
            # ── Train single symbol ──
            symbol = symbol.upper()
            self.stdout.write(f'Training model for: {symbol}\n')
            self.stdout.write('This may take 5-15 minutes...\n\n')

            result = train_symbol(symbol, candles=candles)
            self._print_result(result)

        else:
            # ── Train all symbols ──
            all_symbols = CRYPTO_SYMBOLS + MT5_SYMBOLS
            self.stdout.write(
                f'Training {len(all_symbols)} models...\n'
                f'Estimated time: {len(all_symbols) * 8} minutes\n\n'
            )

            results = []
            for i, sym in enumerate(all_symbols, 1):
                self.stdout.write(
                    f'[{i}/{len(all_symbols)}] Training {sym}...'
                )
                result = train_symbol(sym, candles=candles)
                results.append(result)
                self._print_result(result)
                self.stdout.write('')  # blank line between symbols

            # ── Print final summary ──
            self._print_summary(results)

        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Training complete in {minutes}m {seconds}s\n'
        ))

    def _print_result(self, result: dict):
        """Print result for one symbol."""
        if result['success']:
            accuracy_pct = result['accuracy'] * 100
            color        = (
                self.style.SUCCESS if accuracy_pct >= 60
                else self.style.WARNING
            )
            self.stdout.write(color(
                f"  ✅ {result['symbol']}: "
                f"accuracy={accuracy_pct:.1f}%, "
                f"samples={result['samples']:,}"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"  ❌ {result['symbol']}: FAILED — {result['error']}"
            ))

    def _print_summary(self, results: list):
        """Print training summary table."""
        success = [r for r in results if r['success']]
        failed  = [r for r in results if not r['success']]

        self.stdout.write('\n' + '─' * 50)
        self.stdout.write('TRAINING SUMMARY')
        self.stdout.write('─' * 50)

        self.stdout.write(
            f'Total:   {len(results)} symbols\n'
            f'Success: {len(success)} ✅\n'
            f'Failed:  {len(failed)} ❌\n'
        )

        if success:
            self.stdout.write('\nSuccessful models:')
            for r in sorted(success, key=lambda x: x['accuracy'], reverse=True):
                acc   = r['accuracy'] * 100
                emoji = '🟢' if acc >= 65 else '🟡' if acc >= 55 else '🔴'
                self.stdout.write(
                    f'  {emoji} {r["symbol"]:12} '
                    f'accuracy={acc:.1f}%  '
                    f'samples={r["samples"]:,}'
                )

        if failed:
            self.stdout.write('\nFailed symbols:')
            for r in failed:
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ {r["symbol"]:12} {r["error"]}'
                    )
                )

        # Average accuracy
        if success:
            avg_acc = sum(r['accuracy'] for r in success) / len(success)
            self.stdout.write(
                f'\nAverage accuracy: {avg_acc * 100:.1f}%'
            )

            if avg_acc >= 0.65:
                self.stdout.write(self.style.SUCCESS(
                    '🎯 Good accuracy! Models are ready to use.'
                ))
            elif avg_acc >= 0.55:
                self.stdout.write(self.style.WARNING(
                    '⚠️  Moderate accuracy. Consider more training data.'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    '❌ Low accuracy. Try: --candles 2000'
                ))

        self.stdout.write('─' * 50 + '\n')