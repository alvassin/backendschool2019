from datetime import date, timedelta
from http import HTTPStatus

import pytest

from analyzer.api.schema import BIRTH_DATE_FORMAT
from analyzer.utils.pg import MAX_INTEGER
from analyzer.utils.testing import (
    compare_citizen_groups, generate_citizen, generate_citizens, get_citizens,
    import_data,
)


LONGEST_STR = 'ё' * 256
CASES = (
    # Житель без родственников.
    # Обработчик должен корректно создавать выгрузку с одним жителем.
    (
        [
            generate_citizen(relatives=[])
        ],
        HTTPStatus.CREATED
    ),

    # Житель с несколькими родственниками.
    # Обработчик должен корректно добавлять жителей и создавать
    # родственные связи.
    (
        [
            generate_citizen(citizen_id=1, relatives=[2, 3]),
            generate_citizen(citizen_id=2, relatives=[1]),
            generate_citizen(citizen_id=3, relatives=[1])
        ],
        HTTPStatus.CREATED
    ),

    # Житель сам себе родственник.
    # Обработчик должен позволять создавать такие родственные связи.
    (
        [
            generate_citizen(
                citizen_id=1, name='Джейн', gender='male',
                birth_date='13.09.1945', town='Нью-Йорк', relatives=[1]
            ),
        ],
        HTTPStatus.CREATED
    ),

    # Выгрузка с максимально длинными/большими значениями.
    # aiohttp должен разрешать запросы такого размера, а обработчик не должен
    # на них падать.
    (
        generate_citizens(
            citizens_num=10000,
            relations_num=1000,
            start_citizen_id=MAX_INTEGER - 10000,
            gender='female',
            name=LONGEST_STR,
            town=LONGEST_STR,
            street=LONGEST_STR,
            building=LONGEST_STR,
            apartment=MAX_INTEGER
        ),
        HTTPStatus.CREATED
    ),

    # Пустая выгрузка
    # Обработчик не должен падать на таких данных.
    (
        [],
        HTTPStatus.CREATED
    ),

    # Дата рождения - текущая дата
    (
        [
            generate_citizen(
                birth_date=(date.today()).strftime(BIRTH_DATE_FORMAT)
            )
        ],
        HTTPStatus.CREATED
    ),

    # Дата рождения некорректная (в будущем)
    (
        [
            generate_citizen(
                birth_date=(
                    date.today() + timedelta(days=1)
                ).strftime(BIRTH_DATE_FORMAT)
            )
        ],
        HTTPStatus.BAD_REQUEST
    ),

    # citizen_id не уникален в рамках выгрузки
    (
        [
            generate_citizen(citizen_id=1),
            generate_citizen(citizen_id=1),
        ],
        HTTPStatus.BAD_REQUEST
    ),

    # Родственная связь указана неверно (нет обратной)
    (
        [
            generate_citizen(citizen_id=1, relatives=[2]),
            generate_citizen(citizen_id=2, relatives=[]),
        ],
        HTTPStatus.BAD_REQUEST
    ),

    # Родственная связь c несуществующим жителем
    (
        [
            generate_citizen(citizen_id=1, relatives=[3])
        ],
        HTTPStatus.BAD_REQUEST
    ),

    # Родственные связи не уникальны
    (
        [
            generate_citizen(citizen_id=1, relatives=[2]),
            generate_citizen(citizen_id=2, relatives=[1, 1])
        ],
        HTTPStatus.BAD_REQUEST
    ),
)


@pytest.mark.parametrize('citizens,expected_status', CASES)
async def test_import(api_client, citizens, expected_status):
    import_id = await import_data(api_client, citizens, expected_status)

    # Проверяем, что данные успешно импортированы
    if expected_status == HTTPStatus.CREATED:
        imported_citizens = await get_citizens(api_client, import_id)
        assert compare_citizen_groups(citizens, imported_citizens)
