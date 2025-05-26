import unittest
from collections import deque
from datetime import datetime
from unittest.mock import patch

from stock_analyzer_app.store import DataStore, Insight

class DataStoreTests(unittest.TestCase):

    TEST_MAX_SIZE = 3 # Define a constant for the max_size used in tests

    def setUp(self):
        """
        Set up a fresh DataStore instance before each test,
        patching Django settings for MAX_STORE_SIZE and ensuring reset.
        """
        DataStore._instance = None

        self.settings_patcher = patch(
            'django.conf.settings.MAX_STORE_SIZE',
            new=self.TEST_MAX_SIZE
        )
        self.settings_patcher.start()
        self.addCleanup(self.settings_patcher.stop)

        self.data_store = DataStore()
        self.data_store.data = {}
        self.data_store.insights.clear()


    def test_initialization(self):
        """Test that DataStore initializes correctly with patched settings."""
        self.assertEqual(self.data_store.data, {})
        self.assertIsInstance(self.data_store.insights, deque)
        self.assertEqual(self.data_store.insights.maxlen, self.TEST_MAX_SIZE)

    def test_update_data_new_symbol(self):
        """Test updating data for a new symbol."""
        self.data_store.update_data(
            "AAPL",
            {"last_price": 170.0, "timestamp": 1678886400000}
        )
        self.assertEqual(
            self.data_store.data["AAPL"]["last_price"],
            170.0
        )
        self.assertEqual(
            self.data_store.data["AAPL"]["timestamp"],
            1678886400000
        )

    def test_update_data_existing_symbol(self):
        """Test updating data for an existing symbol."""
        self.data_store.update_data(
            "AAPL",
            {"last_price": 170.0, "timestamp": 1678886400000}
        )
        self.data_store.update_data(
            "AAPL",
            {"last_price": 171.5, "timestamp": 1678886401000}
        )
        self.assertEqual(
            self.data_store.data["AAPL"]["last_price"],
            171.5
        )
        self.assertEqual(
            self.data_store.data["AAPL"]["timestamp"],
            1678886401000
        )

    def test_add_insight(self):
        """Test adding a single insight."""
        insight = Insight(
            "AAPL",
            100.0,
            101.0,
            1.0,
            1678886400000,
            "Price changed"
        )
        self.data_store.add_insight(insight)
        self.assertEqual(len(self.data_store.insights), 1)
        self.assertEqual(self.data_store.insights[0].symbol, "AAPL")

    def test_add_insight_max_size_enforcement(self):
        """Test that max_size is enforced when adding insights."""
        for i in range(self.TEST_MAX_SIZE + 2):
            insight = Insight(
                "AAPL",
                100.0,
                100.0 + i,
                float(i),
                1678886400000 + i,
                f"Insight {i}"
            )
            self.data_store.add_insight(insight)

        self.assertEqual(len(self.data_store.insights), self.TEST_MAX_SIZE)
        self.assertEqual(
            self.data_store.insights[0].message,
            f"Insight {2}"
        )
        self.assertEqual(
            self.data_store.insights[self.TEST_MAX_SIZE - 1].message,
            f"Insight {self.TEST_MAX_SIZE + 1}"
        )

    def test_get_data_specific_symbol(self):
        """Test getting data for a specific symbol."""
        self.data_store.update_data(
            "AAPL", {"last_price": 170.0, "timestamp": 1}
        )
        self.data_store.update_data(
            "MSFT", {"last_price": 280.0, "timestamp": 2}
        )
        aapl_data = self.data_store.get_data("AAPL")
        self.assertEqual(aapl_data["last_price"], 170.0)
        self.assertEqual(self.data_store.get_data("GOOG"), {})

    def test_get_data_all_symbols(self):
        """Test getting data for all symbols."""
        self.data_store.update_data(
            "AAPL", {"last_price": 170.0, "timestamp": 1}
        )
        self.data_store.update_data(
            "MSFT", {"last_price": 280.0, "timestamp": 2}
        )
        all_data = self.data_store.get_data()
        self.assertEqual(len(all_data), 2)
        self.assertIn("AAPL", all_data)
        self.assertIn("MSFT", all_data)

    def test_get_filtered_insights_no_filters(self):
        """Test getting insights with no filters."""
        insight1 = Insight(
            "AAPL",
            100.0,
            101.0,
            1.0,
            1678886400000,
            "I1"
        )
        insight2 = Insight(
            "MSFT",
            200.0,
            204.0,
            2.0,
            1678886401000,
            "I2"
        )
        self.data_store.add_insight(insight1)
        self.data_store.add_insight(insight2)
        insights = self.data_store.get_filtered_insights()
        self.assertEqual(len(insights), 2)
        # MSFT (newer) comes before AAPL (older)
        self.assertEqual(insights[0]['symbol'], "MSFT")
        self.assertEqual(insights[1]['symbol'], "AAPL")

    def test_get_filtered_insights_symbol_filter(self):
        """Test getting insights filtered by symbol."""
        insight1 = Insight(
            "AAPL",
            100.0,
            101.0,
            1.0,
            1678886400000,
            "I1"
        )
        insight2 = Insight(
            "MSFT",
            200.0,
            204.0,
            2.0,
            1678886401000,
            "I2"
        )
        self.data_store.add_insight(insight1)
        self.data_store.add_insight(insight2)
        aapl_insights = self.data_store.get_filtered_insights(symbol="AAPL")
        self.assertEqual(len(aapl_insights), 1)
        self.assertEqual(aapl_insights[0]['symbol'], "AAPL")

    def test_get_filtered_insights_time_filters(self):
        """Test getting insights filtered by time range."""
        ts1 = int(
            datetime(2023, 1, 1, 10, 0, 0).timestamp() * 1000)
        ts2 = int(datetime(2023, 1, 1, 10, 5, 0).timestamp() * 1000)
        ts3 = int(datetime(2023, 1, 1, 10, 10, 0).timestamp() * 1000)

        insight1 = Insight(
            "AAPL",
            100.0,
            101.0,
            1.0,
            ts1,
            "I1"
        )
        insight2 = Insight(
            "MSFT",
            200.0,
            204.0,
            2.0,
            ts2,
            "I2"
        )
        insight3 = Insight(
            "GOOG",
            300.0,
            309.0,
            3.0,
            ts3,
            "I3"
        )

        self.data_store.add_insight(insight1)
        self.data_store.add_insight(insight2)
        self.data_store.add_insight(insight3)

        insights = self.data_store.get_filtered_insights(
            from_timestamp=ts1, to_timestamp=ts3
        )
        self.assertEqual(len(insights), 3)
        # Order is [GOOG, MSFT, AAPL] due to `reversed()`
        self.assertEqual(insights[0]['symbol'], "GOOG")
        self.assertEqual(insights[1]['symbol'], "MSFT")
        self.assertEqual(insights[2]['symbol'], "AAPL")

        insights = self.data_store.get_filtered_insights(
            from_timestamp=ts1, to_timestamp=ts2
        )
        self.assertEqual(len(insights), 2)
        # Order is [MSFT, AAPL]
        self.assertEqual(insights[0]['symbol'], "MSFT")
        self.assertEqual(insights[1]['symbol'], "AAPL")

        insights = self.data_store.get_filtered_insights(
            from_timestamp=ts2 + 1
        )
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]['symbol'], "GOOG")

        insights = self.data_store.get_filtered_insights(
            to_timestamp=ts2 - 1
        )
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]['symbol'], "AAPL")

    def test_get_filtered_insights_limit_offset(self):
        """Test limit and offset pagination."""
        # Ensure the deque is clean for this specific test
        # Explicitly reset DataStore instances for this test as it
        # heavily relies on specific deque state
        DataStore._instances = {}
        self.settings_patcher.stop()
        self.settings_patcher.start()
        self.data_store = DataStore()
        self.data_store.data = {}
        self.data_store.insights.clear()

        NUM_INSIGHTS_TO_ADD = self.TEST_MAX_SIZE + 2
        for i in range(NUM_INSIGHTS_TO_ADD):
            insight = Insight(
                "TEST",
                100.0,
                101.0,
                1.0,
                1000 + i,
                f"Message {i}"
            )
            self.data_store.add_insight(insight)
        # If TEST_MAX_SIZE = 3, insights deque will contain
        # [Message 2, Message 3, Message 4] (oldest to newest)
        # get_filtered_insights (reversed) will return
        # [Message 4, Message 3, Message 2]

        insights = self.data_store.get_filtered_insights(limit=2)
        self.assertEqual(len(insights), 2)
        # Expected: [Message 4, Message 3] (most recent first)
        self.assertEqual(
            insights[0]['message'],
            f"Message {NUM_INSIGHTS_TO_ADD - 1}"
        ) # Message 4
        self.assertEqual(
            insights[1]['message'],
            f"Message {NUM_INSIGHTS_TO_ADD - 2}"
        ) # Message 3

        insights = self.data_store.get_filtered_insights(limit=2, offset=1)
        self.assertEqual(len(insights), 2)
        self.assertEqual(
            insights[0]['message'],
            f"Message {NUM_INSIGHTS_TO_ADD - 2}"
        ) # Message 3
        self.assertEqual(
            insights[1]['message'],
            f"Message {NUM_INSIGHTS_TO_ADD - 3}"
        ) # Message 2

        insights = self.data_store.get_filtered_insights(offset=10)
        self.assertEqual(len(insights), 0)

        insights = self.data_store.get_filtered_insights(
            limit=10, offset=self.TEST_MAX_SIZE - 1
        )
        self.assertEqual(len(insights), 1)
        self.assertEqual(
            insights[0]['message'],
            f"Message {NUM_INSIGHTS_TO_ADD - self.TEST_MAX_SIZE}"
        )