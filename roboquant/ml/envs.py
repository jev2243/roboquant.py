from decimal import Decimal
import logging
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from numpy.typing import NDArray
from roboquant.account import Account

from roboquant.brokers.broker import Broker
from roboquant.brokers.simbroker import SimBroker
from roboquant.event import Event
from roboquant.feeds.eventchannel import EventChannel
from roboquant.feeds.feed import Feed
from roboquant.order import Order
from roboquant.signal import Signal
from roboquant.ml.features import Feature
from roboquant.traders.flextrader import FlexTrader
from roboquant.traders.trader import Trader


logger = logging.getLogger(__name__)


class StrategyEnv(gym.Env):
    # pylint: disable=too-many-instance-attributes,unused-argument

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(
        self,
        obs_feature: Feature,
        reward_feature:  Feature,
        feed: Feed,
        rating_symbols: list[str],
        broker: Broker | None = None,
        trader: Trader | None = None,
    ):
        self.broker: Broker = broker or SimBroker()
        self.trader: Trader = trader or FlexTrader()
        self.channel = EventChannel()
        self.feed = feed
        self.event: Event | None = None
        self.account: Account = self.broker.sync()
        self.symbols = rating_symbols
        self.obs_feature = obs_feature
        self.reward_feature = reward_feature
        self.render_mode = None

        action_size = len(rating_symbols)
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(self.obs_feature.size(),), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(action_size,), dtype=np.float32)
        logger.info("observation_space=%s action_space=%s", self.observation_space, self.action_space)

    def get_observation(self, evt: Event) -> NDArray[np.float32]:
        return self.obs_feature.calc(evt, None)

    def get_reward(self, evt: Event, account: Account):
        return self.reward_feature.calc(evt, account)

    def get_signals(self, action, event):
        return {symbol: Signal(rating) for symbol, rating in zip(self.symbols, action)}

    def step(self, action):
        assert self.event is not None
        assert self.account is not None
        signals = self.get_signals(action, self.event)
        logger.debug("time=%s signals=%s", self.event.time, signals)

        orders = self.trader.create_orders(signals, self.event, self.account)
        self.broker.place_orders(orders)
        self.event = self.channel.get()

        if self.event:
            self.account = self.broker.sync(self.event)
            observation = self.get_observation(self.event)
            reward = self.get_reward(self.event, self.account)
            return observation, reward, False, False, {}

        return None, 0.0, True, False, {}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed, options=options)
        self.broker.reset()
        self.trader.reset()
        self.obs_feature.reset()
        self.reward_feature.reset()

        self.channel = self.feed.play_background()

        while True:
            self.event = self.channel.get()
            assert self.event is not None, "feed empty during warmup"
            self.account = self.broker.sync(self.event)
            self.trader.create_orders({}, self.event, self.account)
            observation = self.get_observation(self.event)
            self.get_reward(self.event, self.account)
            if not np.any(np.isnan(observation)):
                return observation, {}

    def render(self):
        pass

    def __str__(self):
        result = (
            f"TradingEnv(\n\tbroker={self.broker}\n\ttrader={self.trader}\n\tfeed={self.feed}"
            f"\n\tfeatures_size={self.obs_feature.size()}"
            f"\n\tobservation_space={self.observation_space}\n\taction_space={self.action_space}"
            "\n)"
        )
        return result


class TraderEnv(gym.Env):
    # pylint: disable=too-many-instance-attributes,unused-argument

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(
        self,
        obs_feature: Feature,
        reward_feature:  Feature,
        feed: Feed,
        rating_symbols: list[str],
        broker: Broker | None = None,
    ):
        self.broker: Broker = broker or SimBroker()
        self.channel = EventChannel()
        self.feed = feed
        self.event: Event | None = None
        self.account: Account = self.broker.sync()
        self.symbols = rating_symbols
        self.obs_feature = obs_feature
        self.reward_feature = reward_feature

        action_size = len(rating_symbols)
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(obs_feature.size(),), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(action_size,), dtype=np.float32)

        logger.info("observation_space=%s action_space=%s", self.observation_space, self.action_space)

        self.render_mode = None

    def get_observation(self, evt: Event, account) -> NDArray[np.float32]:
        return self.obs_feature.calc(evt, account)

    def get_reward(self, evt: Event, account: Account):
        return self.reward_feature.calc(evt, account)

    def account_rebalance(self, account: Account, new_sizes: dict[str, Decimal]) -> list[Order]:
        orders = []
        for symbol, new_size in new_sizes.items():
            old_size = account.get_position_size(symbol)
            order_size = new_size - old_size
            if order_size != Decimal(0):
                order = Order(symbol, order_size)
                orders.append(order)

        return orders

    def get_orders(self, action, event: Event, account: Account) -> list[Order]:
        new_positions = {}
        equity = account.equity()
        for symbol, fraction in zip(self.symbols, action):
            price = event.get_price(symbol)
            if price:
                rel_fraction = fraction / len(self.symbols)
                contract_value = account.contract_value(symbol, Decimal(1), price)
                size = equity * rel_fraction / contract_value
                new_positions[symbol] = Decimal(size).quantize(Decimal(1))
            else:
                new_positions[symbol] = Decimal()

        return self.account_rebalance(account, new_positions)

    def step(self, action):
        assert self.event is not None
        assert self.account is not None
        logger.debug("time=%s action=%s", self.event.time, action)

        orders = self.get_orders(action, self.event, self.account)
        self.broker.place_orders(orders)
        self.event = self.channel.get()

        if self.event:
            self.account = self.broker.sync(self.event)
            observation = self.get_observation(self.event, self.account)
            reward = self.get_reward(self.event, self.account)
            return observation, reward, False, False, {}

        return None, 0.0, True, False, {}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed, options=options)
        self.broker.reset()
        self.obs_feature.reset()
        self.reward_feature.reset()

        self.channel = self.feed.play_background()

        while True:
            self.event = self.channel.get()
            assert self.event is not None, "feed empty during warmup"
            self.account = self.broker.sync(self.event)
            observation = self.get_observation(self.event, self.account)
            self.get_reward(self.event, self.account)
            if not np.any(np.isnan(observation)):
                return observation, {}

    def render(self):
        pass

    def __str__(self):
        result = (
            f"TradingEnv(\n\tbroker={self.broker}\n\tfeed={self.feed}"
            f"\n\tfeature_size={self.obs_feature.size()}"
            f"\n\tobservation_space={self.observation_space}\n\taction_space={self.action_space}"
            "\n)"
        )
        return result
