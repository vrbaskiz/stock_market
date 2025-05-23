import collections
import time
import threading
import logging

logger = logging.getLogger(__name__)

class Insight:
    """Represents a significant price change insight."""
    __slots__ = ['symbol', 'initial_price', 'current_price', 'change_percent',
                 'event_timestamp_ms', 'message', 'price_change']

    def __init__(self, symbol: str, initial_price: float, current_price: float,
                 change_percent: float, event_timestamp_ms: int, message: str):
        self.symbol = symbol.upper()
        self.initial_price = initial_price
        self.current_price = current_price
        self.change_percent = change_percent
        self.price_change = round(current_price - initial_price)
        self.event_timestamp_ms = event_timestamp_ms
        self.message = message

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "initial_price": self.initial_price,
            "current_price": self.current_price,
            "change_percent": round(self.change_percent, 4), # Round for cleaner output
            "price_change": self.price_change,
            "event_timestamp_ms": self.event_timestamp_ms,
            "event_datetime_utc": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.event_timestamp_ms / 1000)),
        }

class DataStore:
    """
    Singleton class to manage in-memory storage of market data and insights.
    This class is thread-safe and uses locks to ensure data integrity.
    It stores the latest market data (trades) for each symbol and
    significant price change insights in a deque with a maximum size.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, max_size=1000):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DataStore, cls).__new__(cls)
                # Stores latest market data (trades) for each symbol
                cls._instance.data = {}
                cls._instance.data_lock = threading.Lock()

                # Stores historical insights (significant price changes)
                # This needs LRU/max_size as it's a growing list of events
                cls._instance.insights = collections.deque(maxlen=max_size)
                cls._instance.insights_lock = threading.Lock()
                cls._instance.max_size = max_size
                logger.info(f"InMemoryStore initialized with insight max_size={max_size}")
            return cls._instance

    def update_data(self, symbol: str, data: dict):
        """
        Updates the latest market data for a given symbol.
        """
        symbol = symbol.upper()
        with self.data_lock:
            logger.info(f"INSIDE STORE data: {self.data}, instance {self} ")
            self.data[symbol] = data
            logger.debug(f"Updated data for {symbol}: {data}")

    def get_data(self, symbol: str = None):
        """
        Retrieves the latest market data for a specific symbol or all data.
        """
        with self.data_lock:
            logger.info(f"INSIDE STORE data: {self.data}, symbol: {symbol} instance {self} ")
            if symbol:
                a = dict(self.data.get(symbol.upper(), {}))
                logger.info(f"returning data: {a}")
                return a
            a = dict(self.data)
            logger.info(f"returning data: {a}")
            return a # Return a copy of all data

    def get_last_price(self, symbol: str) -> dict | None:
        """
        Retrieves the last known trade price for a given symbol from the store.
        Returns None if no trade data is found.
        """
        symbol = symbol.upper()
        with self.data_lock:
            data = self.data.get(symbol)
            if data and data.get('type') == 'trade':
                return data['data']['price'] # Return the 'data' part of the trade object
            return None

    def add_insight(self, insight: Insight):
        """
        Adds a new insight to the insights deque.
        Deque handles maxlen automatically.
        """
        with self.insights_lock:
            self.insights.append(insight)
            logger.info(
                f"DataStore: Added insight for {insight.symbol}. "
                f"Current insights count: {len(self.insights)}"
            )


    def get_filtered_insights(
            self,
            symbol: str = None,
            from_timestamp: int = None,
            to_timestamp: int = None,
            limit: int = None,
            offset: int = 0
    ):
        """
        Retrieves insights, optionally filtered by symbol and/or timestamp range,
        with pagination (limit and offset).
        """
        filtered = []
        with self.insights_lock:
            # Iterate in reverse to get most recent first, then filter
            for insight in reversed(self.insights):
                # Symbol filter
                if symbol and insight.symbol != symbol.upper():
                    continue

                # Timestamp filters
                if from_timestamp and insight.event_timestamp_ms < from_timestamp:
                    continue
                if to_timestamp and insight.event_timestamp_ms > to_timestamp:
                    continue

                filtered.append(insight.to_dict())

        # Apply offset and limit after filtering
        if offset:
            filtered = filtered[offset:]
        if limit:
            filtered = filtered[:limit]

        logger.debug(f"Retrieved {len(filtered)} insights (symbol={symbol}, from={from_timestamp}, to={to_timestamp}, limit={limit}, offset={offset})")
        return filtered

data_store = DataStore()