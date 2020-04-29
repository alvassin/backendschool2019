"""
При обновлении жителя между разными запросами можеет произойти гонка, в
результате которой БД может прийти в неконсистентное состояние.

Например: есть некий житель без родственников, с citizen_id=1. Выполняется два
конкурентных запроса: первый добавляет жителю #1 родственника #2, второй
добавляет жителю #1 родственника #3.

Ожидается, что запросы должны выполниться последовательно, что в результате у
жителя останется набор родственников из последнего выполненного запроса.

Но может сложиться так, что при выполнении запросов обработчики CitizenView
одновременно получат информацию о жителе и его родственниках из БД.
Каждый обработчик увидит что на данный момент у жителя родственников нет
(соответственно, чтобы привести БД к запрашиваемому состоянию нужно добавить
связь с новым родственником).

В итоге у жителя #1 окажется 2 родственника (#2 и #3). Ситуация может иметь и
более сложные последствия, если для изменения родственников обработчикам
придется не только добавлять, а еще и удалять родственников.

Этот тест в первую очередь воспроизводит эту проблему, доказывая что она есть.
Во вторую очередь он проверяет что в существующем обработчике эта проблема
решена.
"""
import asyncio

import pytest

from analyzer.api.app import create_app
from analyzer.api.handlers import CitizenView
from analyzer.utils.testing import (
    generate_citizens, get_citizens, import_data, patch_citizen,
)


class PatchedCitizenView(CitizenView):
    URL_PATH = r'/with_lock/imports/{import_id:\d+}/citizens/{citizen_id:\d+}'

    async def get_citizen(self, conn, import_id, citizen_id):
        citizen = await super().get_citizen(conn, import_id, citizen_id)

        # Блокируем выполнение других методов, пока все обработчики не
        # прочитают жителя из БД.
        await asyncio.sleep(2)
        return citizen


class PatchedCitizenViewWithoutLock(PatchedCitizenView):
    URL_PATH = r'/no_lock/imports/{import_id:\d+}/citizens/{citizen_id:\d+}'

    @staticmethod
    async def acquire_lock(conn, import_id):
        """
        Отключаем блокировку для получения состояния гонки.
        """


@pytest.fixture
async def api_client(aiohttp_client, arguments, migrated_postgres):
    """
    Добавляем измененные обработчики в сервис. aiohttp требуется создать заново
    (т.к. изменять набор обработчиков после запуска не разрешено).
    """
    app = create_app(arguments)
    app.router.add_route('*', PatchedCitizenView.URL_PATH, PatchedCitizenView)
    app.router.add_route('*', PatchedCitizenViewWithoutLock.URL_PATH,
                         PatchedCitizenViewWithoutLock)
    client = await aiohttp_client(app, server_kwargs={
        'port': arguments.api_port
    })

    try:
        yield client
    finally:
        await client.close()


@pytest.mark.parametrize('url,final_relatives_number', [
    (PatchedCitizenView.URL_PATH, 1),
    (PatchedCitizenViewWithoutLock.URL_PATH, 2)
])
async def test_race_condition(api_client, url, final_relatives_number):
    # Создаем трех жителей, не родственников с citizen_id #1, #2 и #3.
    data = generate_citizens(citizens_num=3, start_citizen_id=1)
    import_id = await import_data(api_client, data)

    # Житель, которому мы будем добавлять родственников
    citizen_id = data[0]['citizen_id']

    # Мы хотим отправить два конкурентных запроса с добавлением новой
    # родственной связи
    seeds = [
        {'relatives': [data[1]['citizen_id']]},
        {'relatives': [data[2]['citizen_id']]}
    ]
    await asyncio.gather(*[
        patch_citizen(api_client, import_id, citizen_id, data=seed,
                      str_or_url=url)
        for seed in seeds
    ])

    # Проверяем кол-во родственников у изменяемого жителя
    # (должно быть равно 1).
    citizens = {
        citizen['citizen_id']: citizen
        for citizen in await get_citizens(api_client, import_id)
    }
    assert len(citizens[citizen_id]['relatives']) == final_relatives_number
