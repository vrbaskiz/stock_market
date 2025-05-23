import logging
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiExample
)
from django.conf import settings

from stock_analyzer_app.store import DataStore
from stock_analyzer_app.stock_manager import get_stock_manager

logger = logging.getLogger(__name__)
# API View for Market Data
@extend_schema(
    summary="Retrieve cached real-time market data (Trades/Quotes)",
    description="Fetches the latest real-time trade or quote data for a "
                "specified symbol from in-memory cache, or all cached data "
                "if no symbol is provided. Data is streamed "
                "from Finnhub WebSockets.",
    parameters=[
        OpenApiParameter(
            name='symbol',
            type=str,
            location=OpenApiParameter.PATH,
            description='The stock ticker symbol (e.g., AAPL, MSFT) '
                        'for which to retrieve data.',
            required=False
        ),
    ],
    responses={
        200: {
            'description': 'Successful retrieval of market data. Data '
                           'represents the latest real-time trade or quote.',
        },
        404: {
            'description': 'Data not found for the specified symbol.',
        }
    }
)
@api_view(['GET'])
def get_cached_market_data(request, symbol=None):
    get_stock_manager()
    ds = DataStore()
    if symbol:
        data = ds.get_data(symbol)
        logger.info(f"All market data: {data}, instance {ds} ")
        logger.info(f"All market data: {ds.data}, instance {ds} ")
        if data:
            return Response(
                data={
                    'symbol': symbol.upper(),
                    'data': data
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                data={'error': f'No data for symbol {symbol}'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        all_data = ds.get_data()
        logger.info(f"All market data: {all_data}, instance {ds} ")
        return Response(
            data={'all_market_data': all_data},
            status=status.HTTP_200_OK
        )


# NEW: API View for ALL Stock Analysis Insights (no symbol in path)
@extend_schema(
    summary="Retrieve all significant stock price change insights with "
            "filtering and pagination",
    description=f"Fetches recorded significant price changes for all monitored"
                f" stocks. Insights are generated based on a "
                f"{settings.PRICE_CHANGE_THRESHOLD}% price change threshold "
                f"for real-time trades. Results can be filtered by a "
                f"timestamp range and paginated.",
    parameters=[
        OpenApiParameter(
            name='from_timestamp',
            type=int,
            location=OpenApiParameter.QUERY,
            description='Start timestamp (Unix milliseconds) for filtering '
                        'insights. Insights with `event_timestamp_ms` less '
                        'than this will be excluded.',
            required=False,
        ),
        OpenApiParameter(
            name='to_timestamp',
            type=int,
            location=OpenApiParameter.QUERY,
            description='End timestamp (Unix milliseconds) for filtering '
                        'insights. Insights with `event_timestamp_ms` greater '
                        'than this will be excluded.',
            required=False,
        ),
        OpenApiParameter(
            name='limit',
            type=int,
            location=OpenApiParameter.QUERY,
            description='Maximum number of insights to return in the response.'
                        ' Default is no limit.',
            required=False,
        ),
        OpenApiParameter(
            name='offset',
            type=int,
            location=OpenApiParameter.QUERY,
            description='Number of insights to skip from the beginning of the '
                        'filtered results. Default is 0.',
            required=False,
        ),
    ],
    responses={
        200: {
            'description': 'Successful retrieval of insights.',
        },
    }
)
@api_view(['GET'])
def get_all_stock_insights(request): # No 'symbol' parameter in signature
    get_stock_manager()
    # Parse query parameters
    from_timestamp = request.query_params.get('from_timestamp')
    to_timestamp = request.query_params.get('to_timestamp')
    limit = request.query_params.get('limit')
    offset = request.query_params.get('offset')

    # Convert parameters to appropriate types (int)
    try:
        from_timestamp = int(from_timestamp) if from_timestamp else None
        to_timestamp = int(to_timestamp) if to_timestamp else None
        limit = int(limit) if limit else None
        offset = int(offset) if offset else None
    except ValueError:
        return Response(
            data={
                'error': 'Invalid timestamp, limit, or offset format. '
                         'Must be integers.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get filtered and paginated insights from the store (symbol=None for all)
    filtered_insights = DataStore().get_filtered_insights(
        symbol=None, # Explicitly pass None for symbol
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        limit=limit,
        offset=offset
    )

    return Response({
        'count': len(filtered_insights),
        'results': filtered_insights
    }, status=status.HTTP_200_OK)


# MODIFIED: API View for Single Symbol Stock Analysis Insights
@extend_schema(
    summary="Retrieve significant stock price change insights for a specific "
            "symbol with filtering and pagination",
    description=f"Fetches recorded significant price changes for a specific "
                f"stock ticker symbol. Insights are generated based on a "
                f"{settings.PRICE_CHANGE_THRESHOLD}% price change threshold "
                f"for real-time trades. Results can be filtered by a timestamp"
                f" range and paginated.",
    parameters=[
        OpenApiParameter(
            name='symbol',
            type=str,
            location=OpenApiParameter.PATH,
            description=f'The stock ticker symbol (AMZN, MSFT, GOOGL) '
                        f'for which to retrieve insights.',
            required=True, # Symbol is required for this path
            enum=[s.upper() for s in settings.STOCKS_TO_ANALYZE]
        ),
        OpenApiParameter(
            name='from_timestamp',
            type=int,
            location=OpenApiParameter.QUERY,
            description='Start timestamp (Unix milliseconds) for filtering '
                        'insights. Insights with `event_timestamp_ms` '
                        'less than this will be excluded.',
            required=False,
        ),
        OpenApiParameter(
            name='to_timestamp',
            type=int,
            location=OpenApiParameter.QUERY,
            description='End timestamp (Unix milliseconds) for filtering insights. Insights with `event_timestamp_ms` greater than this will be excluded.',
            required=False,
        ),
        OpenApiParameter(
            name='limit',
            type=int,
            location=OpenApiParameter.QUERY,
            description='Maximum number of insights to return in the response. Default is no limit.',
            required=False,
        ),
        OpenApiParameter(
            name='offset',
            type=int,
            location=OpenApiParameter.QUERY,
            description='Number of insights to skip from the beginning of the '
                        'filtered results. Default is 0.',
            required=False,
        ),
    ],
    responses={
        200: {
            'description': 'Successful retrieval of insights.',
        },
        404: {
            'description': 'Symbol not found or no insights for the symbol.',
        }
    }
)
@api_view(['GET'])
def get_symbol_stock_insights(request, symbol):
    get_stock_manager()
    """
    API View for retrieving significant stock price change insights for a
    specific symbol. This view allows filtering by timestamp, range and
    pagination.

    :param request: The HTTP request object.
    :param symbol: The stock ticker symbol (GOOGL, AMZN, MSFT) for which to
                    retrieve insights.
    """
    # Parse query parameters
    from_timestamp = request.query_params.get('from_timestamp')
    to_timestamp = request.query_params.get('to_timestamp')
    limit = request.query_params.get('limit')
    offset = request.query_params.get('offset')

    try:
        from_timestamp = int(from_timestamp) if from_timestamp else None
        to_timestamp = int(to_timestamp) if to_timestamp else None
        limit = int(limit) if limit else None
        offset = int(offset) if offset else None
    except ValueError:
        return Response(
            data={
                'error': 'Invalid timestamp, limit, or offset format. '
                         'Must be integers.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get filtered and paginated insights for the specific symbol
    filtered_insights = DataStore().get_filtered_insights(
        symbol=symbol, # Pass the symbol from the path
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        limit=limit,
        offset=offset
    )

    # For /insights/<symbol>/, return insights under an 'insights' key
    return Response({
        'symbol': symbol.upper(),
        'insights': filtered_insights
    }, status=status.HTTP_200_OK)


# View for the HTML Test Page
def api_tester_page(request):
    """
    Renders the HTML page for interactively testing the REST API.
    """
    get_stock_manager()
    # No context needed for this simple static page
    return render(request, 'api_tester.html', {})
