from abc import ABC, abstractmethod

from roboquant.account import Account
from roboquant.event import Event
from roboquant.order import Order


class Journal(ABC):
    """
    A journal enables the tracking and/or logging of one or more metrics during a run.

    A journal can hold detailed records of all your trading activities in the financial markets.
    It serves as a tool to track and analyze their performance, decisions, and outcomes over time
    """

    @abstractmethod
    def track(self, event: Event, account: Account, orders: list[Order]):
        """invoked at each step of a run that provides the journal with the opportunity to
        track and log various metrics."""
        ...

    def reset(self):
        """reset the state of the journal, default is to do nothing"""
