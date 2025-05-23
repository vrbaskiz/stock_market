Finnhub Real-Time Market Data & Insights API

This project provides a Django REST API for real-time stock market data and analysis insights, leveraging the Finnhub WebSocket API. It features an in-memory data store for live data and historical significant price changes, accessible via REST endpoints and a simple web-based API tester.

Technologies Used

* Backend:
    * Python 3.x
    * Django
    * Django REST Framework
    * websocket-client: For Finnhub WebSocket connectivity.
    * drf-spectacular: For OpenAPI 3.0 schema generation and Swagger UI/Redoc.
* Frontend (API Tester):
    * HTML, CSS (Tailwind CSS CDN), JavaScript
* Configuration:
    * Environment Variables (managed via Bash script)

Project Structure

    stock_market/
    ├── stock_market/
    │   ├── __init__.py
    │   ├── asgi.py           # ASGI config (if using Channels)
    │   ├── settings.py       # Django project settings (reads env vars)
    │   ├── urls.py           # Project-level URL routing
    │   └── wsgi.py           # WSGI config
    ├── stock_analyzer_app/
    │   ├── __init__.py       # App config
    │   ├── apps.py           # AppConfig to start StockManager
    │   ├── store.py          # In-memory data store (latest data & insights)
    │   ├── stock_manager.py  # Finnhub WebSocket client and data processing
    │   ├── templates/
    │   │   └── api_tester.html # Web-based API tester UI
    │   └── views.py          # Django REST Framework API views
    ├── .env                  # Environment variables (DO NOT COMMIT TO GIT)
    ├── .gitignore            # Git ignore file
    ├── manage.py             # Django management script
    ├── requirements.txt      # Python dependencies
    └── start_dev.sh          # Bash script to run server with env vars

Setup and Installation

1. Clone the Repository

       git clone <your-repository-url>
       cd stock_market

2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment to manage dependencies.

      python3 -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install Dependencies

       pip install -r requirements.txt


5. Configure Environment Variables

Create a .env file in the root directory of your project (same level as manage.py)

      # .env
      DJANGO_SECRET_KEY='your-very-long-and-secret-django-key'
      FINNHUB_API_KEY='YOUR_FINNHUB_API_KEY'
      DJANGO_DEBUG=True

* DJANGO_SECRET_KEY: Generate a strong key using python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'.
* FINNHUB_API_KEY: Obtain your free API key from Finnhub.io.
* DJANGO_DEBUG: Set to True for development, False for production.

5. Make the start_dev.sh Script Executable if needed:

       chmod +x start_dev.sh

6. Start the Development Server

Use the provided start_dev.sh script to load environment variables and run the server:

    ./start_dev.sh

The server will typically run on http://127.0.0.1:8000/.

---

# API Endpoints

## Market Data

* Get All Latest Market Data:
    * GET /market-data/
    * Retrieves the latest trade/quote data for all symbols currently in the in-memory cache.
* Get Latest Market Data for a Specific Symbol:
    * GET /market-data/<str:symbol>/
    * Retrieves the latest trade/quote data for the specified stock symbol (e.g., /api/market-data/AAPL/).

## Analysis Insights

* Get All Significant Price Change Insights:
    * GET /insights/
    * Retrieves a paginated list of all recorded significant price change insights across all monitored symbols.
    * Query Parameters:
        * from_timestamp (int, optional): Start timestamp (Unix milliseconds).
        * to_timestamp (int, optional): End timestamp (Unix milliseconds).
        * limit (int, optional): Maximum number of insights to return.
        * offset (int, optional): Number of insights to skip.
* Get Significant Price Change Insights for a Specific Symbol:
    * GET /insights/<str:symbol>/
    * Retrieves a paginated list of significant price change insights for the specified stock symbol (e.g., /api/insights/AMZN/).
    * Query Parameters: (Same as above)

---

API Documentation (Swagger UI / Redoc)

Once the server is running, you can access the interactive API documentation:

* Swagger UI: http://127.0.0.1:8000/api/schema/swagger-ui/
* Redoc: http://127.0.0.1:8000/api/schema/redoc/

---

Web API Tester

A simple HTML page is provided to test the API endpoints directly from your browser:

* API Tester Page: http://127.0.0.1:8000/api-tester/

This page dynamically constructs API calls based on your input and displays the JSON responses.

---

Deployment

For deployment to a cloud environment (e.g., Heroku, AWS, DigitalOcean, Docker):

1.  Environment Variables: configure DJANGO_SECRET_KEY and FINNHUB_API_KEY directly in your hosting platform's environment variable settings. Set DJANGO_DEBUG to False in production.
2.  ALLOWED_HOSTS: Update ALLOWED_HOSTS in my_stock_analyzer/settings.py to include your production domain(s).
3.  Static Files: For production, you'll need to configure Django to serve static files (like your api_tester.html if served directly by Django) properly, typically using collectstatic and a web server like Nginx or a CDN.
4.  WSGI Server: Use a production-ready WSGI server like Gunicorn or uWSGI.

---
