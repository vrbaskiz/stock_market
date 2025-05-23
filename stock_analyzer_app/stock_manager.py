import threading
import json
import websocket
import ssl
import logging

from django.conf import settings
from stock_analyzer_app.store import data_store, Insight

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
            if symbol and symbol.upper() in self.stocks_to_analyze:
                # Finnhub trade data structure
                trade_info = {
                    "price": trade_data_item.get('p'),
                    "size": trade_data_item.get('s'),
                    "timestamp": trade_data_item.get('t'),
                    "exchange": trade_data_item.get('x', 'N/A'),
                }
                logger.info(f"DATA STORE instance {data_store} ")
                last_data = data_store.get_data(symbol)

                last_price = last_data.get('data', {}).get('price', None)
                current_price = trade_info['price']

                logger.debug(
                    f"[{symbol}] Received trade: "
                    f"Price={current_price}, LastPrice={last_price}"
                )
                # Update the data store with the latest trade info
                data_store.update_data(
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
                        data_store.add_insight(insight_obj)
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
        self.running = False

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
        try:
            self.ws_app = websocket.WebSocketApp(
                self.fh_ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            logger.info("Starting Finnhub WebSocketApp run_forever...")
            self.ws_app.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            logger.info("Finnhub WebSocketApp run_forever exited.")
        except Exception as e:
            logger.critical(f"Critical error in Finnhub WebSocket thread: {e}")
        finally:
            self.running = False

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
        if self.running and self.ws_app:
            logger.info("Stopping StockManager...")
            self.running = False
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
