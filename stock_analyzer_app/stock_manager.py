import threading
import json
import websocket
import ssl
import time
import logging

from django.conf import settings
from stock_analyzer_app.store import DataStore, Insight

logger = logging.getLogger(__name__)

class MESSAGE_TYPE:
    """
    Enum-like class to define message types for the WebSocket API.
    """
    TRADE = 'trade'
    PING = 'ping'
    SUBSCRIPTION_CONFIRMATION = 'type'

class StockManager:
    """
    Singleton class to manage the Finnhub WebSocket connection.
    This class handles the connection to the Finnhub WebSocket API,
    subscribes to stock symbols, and processes incoming messages.
    It also manages the data store for market data and insights.
    The class is thread-safe and ensures that only one instance
    of the WebSocket connection is active at any time.
    """
    _instance = None
    _lock = threading.Lock()

    RECONNECT_INITIAL_DELAY = 5    # seconds for first retry
    RECONNECT_MAX_DELAY = 60       # seconds for maximum retry delay
    MAX_RECONNECT_ATTEMPTS = 100   # Maximum number of reconnection attempts


    def __new__(cls, api_key: str):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StockManager, cls).__new__(cls)
                cls._instance.api_key = api_key
                cls._instance.ws_app = None # WebSocketApp instance
                cls._instance.running = False
                cls._instance.thread = None
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            logger.info("Initializing StockManager...")

            # Load configuration from Django settings
            self.stocks_to_analyze = settings.STOCKS_TO_ANALYZE
            self.threshold = settings.PRICE_CHANGE_THRESHOLD
            self.fh_ws_url = (f"{settings.FINNHUB_CONFIG['WEBSOCKET_URL']}"
                              f"?token={self.api_key}")

            logger.info(f"Configured to analyze via Finnhub WebSocket.")
            self.start()

    def _on_message(self, ws, message):
        """Callback for when a message is received from the WebSocket."""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            match message_type:
                case MESSAGE_TYPE.TRADE:
                    self.process_trade_message(data)
                case MESSAGE_TYPE.PING:
                    logger.debug("Finnhub WS: Ping received")
                    pass
                case MESSAGE_TYPE.SUBSCRIPTION_CONFIRMATION:
                    logger.info(
                        f"Finnhub WS: "
                        f"{data.get('data', 'Subscription confirmation')}"
                    )
                case _:
                    logger.warning(
                        f"Finnhub WS: Received unhandled message type: "
                        f"{message_type} - {data}")

        except json.JSONDecodeError as e:
            logger.error(
                f"Finnhub WS: Error decoding JSON message: "
                f"{e} - Message: {message}"
            )
        except Exception as e:
            logger.error(
                f"Finnhub WS: Error processing message: "
                f"{e} - Message: {message}")

    def process_trade_message(self, data):
        """
        Processes trade messages from the WebSocket.
        This method checks if the symbol is in the list of stocks to analyze,
        and if so, it calculates the price change and generates insights.
        Additionally, this method updates the data store with the latest trade.
        :param data: The data received from the WebSocket.
        :return: None
        """
        for trade_data_item in data.get('data', []):
            symbol = trade_data_item.get('s')
            ds = DataStore()
            if symbol and symbol.upper() in self.stocks_to_analyze:
                # Finnhub trade data structure
                trade_info = {
                    "price": trade_data_item.get('p'),
                    "size": trade_data_item.get('s'),
                    "timestamp": trade_data_item.get('t'),
                    "exchange": trade_data_item.get('x', 'N/A'),
                }
                last_data = ds.get_data(symbol)

                last_price = last_data.get('data', {}).get('price', None)
                current_price = trade_info['price']

                # Update the data store with the latest trade info
                ds.update_data(
                    symbol, {'type': 'trade', 'data': trade_info}
                )
                # If there is last_price to calculate change
                if last_price is not None:
                    price_change = current_price - last_price
                    # Calculate percentage change (div by 0 check)
                    pct_change = 0
                    if last_price != 0:
                        pct_change = (price_change / last_price) * 100

                    logger.debug(
                        f"[{symbol}] Calculated change: "
                        f"AbsChange={round(price_change, 4)}, "
                        f"PctChange={round(pct_change, 4)}%"
                    )

                    if abs(pct_change) >= self.threshold:
                        # Create an Insight object
                        inf = 'increase' if pct_change > 0 else 'decrease'
                        insight_obj = Insight(
                            symbol=symbol.upper(),
                            initial_price=last_price,
                            current_price=current_price,
                            change_percent=round(pct_change, 4),
                            event_timestamp_ms=trade_info['timestamp'],
                            message=f"Significant price {inf} of "
                                    f"{abs(pct_change):.2f}%"
                        )
                        ds.add_insight(insight_obj)
                        logger.info(
                            f"[{symbol}] {insight_obj.message} "
                            f"(Old: {last_price}, New: {current_price})"
                        )
                    else:
                        logger.debug(
                            f"[{symbol}] Change {round(pct_change, 4)}%"
                            f" is below threshold {self.threshold}%. "
                            f"No insight generated."
                        )
                else:
                    logger.debug(
                        f"[{symbol}] First trade received. "
                        f"Setting last_price to {current_price}. "
                        f"No insight calculated yet."
                    )

    def _on_error(self, ws, error):
        """Callback for WebSocket errors."""
        logger.error(f"Finnhub WS Error: {error}")

    def _on_close(self, ws, close_status_code, close_message):
        """Callback for WebSocket close event."""
        logger.info(
            f"Finnhub WS Closed: {close_status_code} - {close_message}"
        )

    def _on_open(self, ws):
        """Callback for when the WebSocket connection is opened."""
        logger.info("Finnhub WS connection opened. Subscribing...")
        for symbol in self.stocks_to_analyze:
            ws.send(json.dumps({"type":"subscribe","symbol":symbol.upper()}))
            logger.info(f"Subscribed to {symbol.upper()}")

    def _run_websocket_in_thread(self):
        """
        Runs the WebSocketApp in a dedicated thread.
        This method blocks until the WebSocket connection closes.
        """
        reconnect_attempt = 0
        current_delay = self.RECONNECT_INITIAL_DELAY
        while self.running:
            try:
                self.ws_app = websocket.WebSocketApp(
                    self.fh_ws_url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                logger.info(
                    f"Attempting WS connection "
                    f"(Attempt {reconnect_attempt + 1})..."
                )
                self.ws_app.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                logger.info("Finnhub WebSocketApp run_forever exited.")
                if not self.running:
                    logger.info(
                        "StockManager intentionally stopped. "
                        "Exiting reconnection loop."
                    )
                    break

                # If we reach here,  connection was lost
                reconnect_attempt += 1
                # commented out just because of my incorrect expectation
                # of how many times it should try to reconnect
                # and how long stock market could be down, lose connection
                # if reconnect_attempt > self.MAX_RECONNECT_ATTEMPTS:
                #     logger.critical(
                #         f"Maximum reconnection attempts "
                #         f"({self.MAX_RECONNECT_ATTEMPTS}) reached. Giving up."
                #     )
                #     self.running = False
                #     break

                # Apply exponential backoff delay before next retry
                logger.warning(
                    f"WS disconnected unexpectedly. "
                    f"Reconnecting in {current_delay}s "
                    f"(Attempt {reconnect_attempt})..."
                )
                time.sleep(current_delay)
                current_delay = min(
                    current_delay * 2, self.RECONNECT_MAX_DELAY
                )

            except Exception as e:
                logger.error(
                    f"Critical error in Finnhub WebSocket thread: {e}"
                )
            # I want to try to reconnect even if there is an error
            # also changed log above to be error since I know error level shows
            # finally:
            #     self.running = False

    def start(self):
        """Starts the Finnhub WebSocket client in a new daemon thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(
                target=self._run_websocket_in_thread, daemon=True
            )
            self.thread.start()
            logger.info("StockManager thread launched.")

    def stop(self):
        """Stops the Finnhub WebSocket client."""
        if self.running:
            logger.info("Stopping StockManager...")
            self.running = False
            if self.ws_app:
                logger.info("Closing WebSocket connection...")
                self.ws_app.close()
            if self.thread:
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    logger.warning(
                        "StockManager thread did not terminate gracefully."
                    )
            logger.info("StockManager stopped.")

stock_manager_instance = None

def get_stock_manager():
    global stock_manager_instance
    if stock_manager_instance is None:
        api_key = settings.FINNHUB_CONFIG['API_KEY']
        stock_manager_instance = StockManager(api_key)
    return stock_manager_instance
