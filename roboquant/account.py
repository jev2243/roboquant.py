from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from roboquant.asset import Asset
from roboquant.order import Order
from roboquant.monetary import Amount, Wallet, USD, Currency


@dataclass(slots=True)
class Position:
    """Position of an asset"""

    size: Decimal
    """Position size"""

    avg_price: float
    """Average price paid denoted in the currency of the asset"""

    mkt_price: float
    """latest market price denoted in the currency of the asset"""

    @property
    def is_short(self):
        return self.size < 0

    @property
    def is_long(self):
        return self.size > 0


class Account:
    """Represents a trading account with all monetary amounts denoted in a single currency.
    The account maintains the following state during a run:

    - Available buying power for orders in the base currency of the account.
    - Cash available in the base currency of the account.
    - The open positions.
    - The open orders.
    - Calculated derived equity value of the account in the base currency of the account.
    - The last time the account was updated.

    Only the broker updates the account and does this only during its `sync` method.
    """

    __slots__ = "buying_power", "positions", "orders", "last_update", "cash"

    def __init__(self, base_currency: Currency = USD):
        self.buying_power: Amount = Amount(base_currency, 0.0)
        self.positions: dict[Asset, Position] = {}
        self.orders: list[Order] = []
        self.last_update: datetime = datetime.fromisoformat("1900-01-01T00:00:00+00:00")
        self.cash: Wallet = Wallet()

    @property
    def base_currency(self) -> Currency:
        """Return the base currency of this account"""
        return self.buying_power.currency

    def mkt_value(self) -> Wallet:
        """Return the sum of the market values of the open positions in the account.
        """
        result = Wallet()
        for asset, position in self.positions.items():
            result += asset.contract_amount(position.size, position.mkt_price)
        return result

    def convert(self, x: Wallet | Amount) -> float:
        """convert a wallet or amount into the base currency of the account"""
        return x.convert_to(self.base_currency, self.last_update)

    def position_value(self, asset: Asset) -> float:
        """Return position value denoted in the base currency of the account."""
        pos = self.positions.get(asset)
        return asset.contract_value(pos.size, pos.mkt_price) if pos else 0.0

    def short_positions(self) -> dict[Asset, Position]:
        """Return al the short positions in the account"""
        return {symbol: position for (symbol, position) in self.positions.items() if position.is_short}

    def long_positions(self) -> dict[Asset, Position]:
        """Return al the long positions in the account"""
        return {symbol: position for (symbol, position) in self.positions.items() if position.is_long}

    def contract_value(self, asset: Asset, size: Decimal, price: float) -> float:
        """Contract value denoted in the base currency of hte account"""
        return asset.contract_amount(size, price).convert_to(self.base_currency, self.last_update)

    def equity(self) -> Wallet:
        """Return the equity of the account.
        It calculates the sum mkt values of each open position and adds the available cash.

        The returned value is denoted in the base currency of the account.
        """
        return self.cash + self.mkt_value()

    def equity_value(self) -> float:
        """Return the equity value denoted in the base currency of the account"""
        return self.convert(self.equity())

    def unrealized_pnl(self) -> Wallet:
        """Return the sum of the unrealized profit and loss for the open position.

        The returned value is denoted in the base currency of the account.
        """
        result = Wallet()
        for asset, position in self.positions.items():
            result += asset.contract_amount(position.size, position.mkt_price - position.avg_price)
        return result

    def required_buying_power(self, order: Order) -> Amount:
        """Return the amount of buying power required for a certain order. The underlying logic takes into
        account that a reduction is position size doesn't require buying power.
        """
        pos_size = self.get_position_size(order.asset)

        # only additional required if remaining order size would increase position size
        if abs(pos_size + order.remaining) > abs(pos_size):
            return order.asset.contract_amount(abs(order.remaining), order.limit)

        return Amount(order.asset.currency, 0.0)

    def unrealized_pnl_value(self) -> float:
        return self.convert(self.unrealized_pnl())

    def get_position_size(self, asset: Asset) -> Decimal:
        """Return the position size for a symbol"""
        pos = self.positions.get(asset)
        return pos.size if pos else Decimal()

    def __repr__(self) -> str:
        p = [f"{v.size}@{k.symbol}" for k, v in self.positions.items()]
        p_str = ", ".join(p) or "none"

        o = [f"{o.size}@{o.asset.symbol}" for o in self.orders]
        o_str = ", ".join(o) or "none"

        mkt = self.mkt_value() or Amount(self.base_currency, 0.0)

        result = (
            f"buying power : {self.buying_power}\n"
            f"cash         : {self.cash}\n"
            f"equity       : {self.equity()}\n"
            f"positions    : {p_str}\n"
            f"mkt value    : {mkt}\n"
            f"orders       : {o_str}\n"
            f"last update  : {self.last_update}"
        )
        return result
