from abc import abstractmethod

from roboquant.asset import Asset
from roboquant.event import Event
from roboquant.signal import Signal
from roboquant.strategies.buffer import OHLCVBuffers, OHLCVBuffer
from roboquant.strategies.strategy import Strategy


class TaStrategy(Strategy):
    """Abstract base class for other strategies that helps to implement trading solutions
    based on technical indicators using a history of bars (aka candlesticks).

    Subclasses should implement the `process_asset` method. This method is only invoked once
    there is at least `size` history for an individual asset available.
    """

    def __init__(self, size: int) -> None:
        super().__init__()
        self._data = OHLCVBuffers(size)
        self.size = size

    def create_signals(self, event: Event) -> list[Signal]:
        result: list[Signal] = []
        assets = self._data.add_event(event)
        for asset in assets:
            ohlcv = self._data[asset]
            if signal := self.process_asset(asset, ohlcv):
                result.append(signal)
        return result

    @abstractmethod
    def process_asset(self, asset: Asset, ohlcv: OHLCVBuffer) -> Signal | None:
        """
        Create a signal for the provided asset, or return None if no signal should be created.
        Subclasses should implement this method.

        Sample:
        ```
        prices = ohlcv.close()
        if prices[-10:].mean() > prices[-20:].mean():
            return Signal.buy(asset)
        ```
        """
        ...
