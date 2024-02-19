import os
import time
from roboquant import Roboquant, BasicTracker, CSVFeed, EMACrossover

if __name__ == "__main__":
    start = time.time()
    path = os.path.expanduser("~/data/nyse_stocks/")
    feed = CSVFeed.stooq_us_daily(path)
    loadtime = time.time() - start
    rq = Roboquant(EMACrossover(13, 26))
    tracker = BasicTracker()
    start = time.time()
    account = rq.run(feed, tracker=tracker)
    runtime = time.time() - start

    print(account)
    print(tracker)

    # Print statistics
    print()
    print(f"load time  = {loadtime:.1f}s")
    print("files      =", len(feed.symbols))
    print(f"throughput = {len(feed.symbols) / loadtime:.0f} files/s")
    print(f"run time   = {runtime:.1f}s")
    candles = tracker.items
    print(f"candles    = {(candles / 1_000_000):.1f}M")
    throughput = candles / (runtime * 1_000_000)
    print(f"throughput = {throughput:.1f}M candles/s")
    print()
