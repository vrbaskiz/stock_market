from django.apps import AppConfig


class StockAnalyzerAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stock_analyzer_app'

    def ready(self):
        # import stock_analyzer_app.stock_manager as sm

        print("AppConfig ready(): Starting PolygonWebSocketManager...")