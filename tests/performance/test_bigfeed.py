import os
import time
import unittest

import roboquant as rq


class TestBigFeed(unittest.TestCase):
    """Run two large bast tests, one over daily bars and one over 5-minutes bars"""

    @staticmethod
    def _print(account, journal, feed, load_time, runtime):
        print("", account, journal, sep="\n\n")

        # Print statistics
        print()
        print(f"load time  = {load_time:.1f}s")
        print("files      =", len(feed.symbols))
        print(f"throughput = {len(feed.symbols) / load_time:.0f} files/s")
        print(f"run time   = {runtime:.1f}s")
        candles = journal.items / 1_000_000.0
        print(f"candles    = {candles:.1f}M")
        throughput = candles / runtime
        print(f"throughput = {throughput:.1f}M candles/s")
        print()

    def _run(self, feed, journal: rq.journals.BasicJournal):
        strategy = rq.strategies.EMACrossover(13, 26)
        start = time.time()
        account = rq.run(feed, strategy, journal=journal)

        self.assertTrue(journal.items > 1_000_000)
        self.assertTrue(journal.buy_orders + journal.sell_orders > 1_000)
        self.assertTrue(journal.events > 1_000)

        return account, time.time() - start

    def test_big_feed_daily(self):
        start = time.time()
        path = os.path.expanduser("~/data/nyse_stocks/")
        feed = rq.feeds.CSVFeed.stooq_us_daily(path)
        load_time = time.time() - start

        journal = rq.journals.BasicJournal()
        account, runtime = self._run(feed, journal)
        self._print(account, journal, feed, load_time, runtime)

    def test_big_feed_intraday(self):
        start = time.time()
        path = os.path.expanduser("~/data/intra/")
        feed = rq.feeds.CSVFeed.stooq_us_intraday(path)
        load_time = time.time() - start

        journal = rq.journals.BasicJournal()
        account, runtime = self._run(feed, journal)
        self._print(account, journal, feed, load_time, runtime)


if __name__ == "__main__":
    unittest.main()
