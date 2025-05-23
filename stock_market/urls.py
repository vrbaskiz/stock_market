"""
URL configuration for stock_market project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from stock_analyzer_app import views
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [

    path(
        route='api/schema/',
        view=SpectacularAPIView.as_view(),
        name='schema'
    ),
    path(
        route='api/docs/',
        view=SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui'
    ),

    # API endpoints for market data
    path(
        route='market-data/',
        view=views.get_cached_market_data,
        name='all_market_data'
    ),
    path(
        route='market-data/<str:symbol>/',
        view=views.get_cached_market_data,
        name='symbol_market_data'
    ),

    # API endpoints for stock insights
    path(
        route='insights/',
        view=views.get_all_stock_insights,
        name='all_stock_insights'
    ),
    path(
        route='insights/<str:symbol>/',
        view=views.get_symbol_stock_insights,
        name='symbol_stock_insights'
    ),

    # URL for the HTML API Tester page
    path(
        route='api-tester/',
        view=views.api_tester_page,
        name='api_tester_page'
    ),
]