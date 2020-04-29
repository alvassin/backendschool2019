"""
Проверяется что ошибки сервиса возвращаются в правильном формате в JSON.
"""
from http import HTTPStatus

import pytest
from aiohttp.web_exceptions import HTTPBadRequest
from aiohttp.web_request import Request

from analyzer.api.app import create_app
from analyzer.api.schema import ErrorResponseSchema


async def unexpected_error(_: Request):
    """
    Обработчик с внутренним исключением.
    """
    raise RuntimeError('Message with internal information')


async def http_error_without_json_payload(_: Request):
    """
    Обработчик с веб-исключением.
    """
    raise HTTPBadRequest(text='some error happened')


@pytest.fixture
async def api_client(aiohttp_client, arguments, migrated_postgres):
    """
    Для регистрации обработчиков имитирующих ошибки необходимо создать
    новый объект Application (aiohttp не разрешает регистрацию обработчиков в
    запущенном приложении).
    """
    app = create_app(arguments)
    app.router.add_post('/unexpected-error', unexpected_error)
    app.router.add_post('/http-error-without-json-payload',
                        http_error_without_json_payload)
    client = await aiohttp_client(app, server_kwargs={
        'port': arguments.api_port
    })

    try:
        yield client
    finally:
        await client.close()


@pytest.mark.parametrize('url,error_message', [
    ('/unexpected-error', HTTPStatus.INTERNAL_SERVER_ERROR.description),
    ('/http-error-without-json-payload', 'some error happened'),
    ('/imports', 'Request validation has failed')
])
async def test_server_error(api_client, url, error_message):
    response = await api_client.post(url)
    data = await response.json()

    errors = ErrorResponseSchema().validate(data)
    assert errors == {}

    assert data['error']['message'] == error_message
