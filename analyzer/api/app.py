import logging
from functools import partial
from types import AsyncGeneratorType, MappingProxyType
from typing import AsyncIterable, Mapping

from aiohttp import PAYLOAD_REGISTRY
from aiohttp.web_app import Application
from aiohttp_apispec import setup_aiohttp_apispec, validation_middleware
from configargparse import Namespace

from analyzer.api.handlers import HANDLERS
from analyzer.api.middleware import error_middleware, handle_validation_error
from analyzer.api.payloads import AsyncGenJSONListPayload, JsonPayload
from analyzer.utils.pg import setup_pg


# По умолчанию размер запроса к aiohttp ограничен 1 мегабайтом:
# https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.Application
# Размер запроса со 10 000 жителей и 2000 связей (с учетом максимальной длины
# строк и кодировки json с параметром ensure_ascii=True) может занимать
# ~63 мегабайт:
MEGABYTE = 1024 ** 2
MAX_REQUEST_SIZE = 70 * MEGABYTE

log = logging.getLogger(__name__)


def create_app(args: Namespace) -> Application:
    """
    Создает экземпляр приложения, готового к запуску.
    """
    app = Application(
        client_max_size=MAX_REQUEST_SIZE,
        middlewares=[error_middleware, validation_middleware]
    )

    # Подключение на старте к postgres и отключение при остановке
    app.cleanup_ctx.append(partial(setup_pg, args=args))

    # Регистрация обработчиков
    for handler in HANDLERS:
        log.debug('Registering handler %r as %r', handler, handler.URL_PATH)
        app.router.add_route('*', handler.URL_PATH, handler)

    # Swagger документация
    setup_aiohttp_apispec(app=app, title='Citizens API', swagger_path='/',
                          error_callback=handle_validation_error)

    # Автоматическая сериализация в json данных в HTTP ответах
    PAYLOAD_REGISTRY.register(AsyncGenJSONListPayload,
                              (AsyncGeneratorType, AsyncIterable))
    PAYLOAD_REGISTRY.register(JsonPayload, (Mapping, MappingProxyType))
    return app
