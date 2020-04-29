"""
Тест зависит от времени.

В PostgreSQL обработчик рассчитывает возраст жителя используя его дату рождения
и базовую дату (по умолчанию равна текущей), изменяется в
analyzer.api.handlers.TownAgeStatView.CURRENT_DATE

В Python используется только функция age2date для более удобного представления
возврастов жителей в тесте, которая позволяет подменить базовую дату с помощью
параметра base_date.
"""
from copy import copy
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
import pytz

from analyzer.api.schema import BIRTH_DATE_FORMAT
from analyzer.utils.testing import (
    generate_citizen, get_citizens_ages, import_data,
)


CURRENT_DATE = datetime(2020, 2, 17, tzinfo=pytz.utc)


def age2date(years: int, days: int = 0, base_date=CURRENT_DATE) -> str:
    """
    Возвращает дату рождения для жителя, возраст которого составляет years лет
    и days дней. Дата рассчитывается исходя из базовой CURRENT_DATE.

    Позволяет представлять дату рождения жителя в виде возраста человека в днях
    и годах, что гораздо нагляднее в тестах.
    """
    birth_date = copy(base_date).replace(year=base_date.year - years)
    birth_date -= timedelta(days=days)
    return birth_date.strftime(BIRTH_DATE_FORMAT)


datasets = [
    # Несколько жителей у которых завтра день рождения.
    # Проверяется что обработчик использует в рассчетах количество полных лет.
    {
        'citizens': [
            generate_citizen(birth_date=age2date(years=10, days=364),
                             town='Москва', citizen_id=1),
            generate_citizen(birth_date=age2date(years=30, days=364),
                             town='Москва', citizen_id=2),
            generate_citizen(birth_date=age2date(years=50, days=364),
                             town='Москва', citizen_id=3)
        ],
        'expected': [
            {
                'town': 'Москва',
                'p50': 30.,
                'p75': 40.,
                'p99': 49.6
            }
        ]
    },

    # Житель у которого сегодня день рождения.
    # Проверяет краевой случай, возраст жителя у которого сегодня день рождения
    # не должен рассчитаться как на 1 год меньше.
    {
        'citizens': [
            generate_citizen(birth_date=age2date(years=10),
                             town='Москва')
        ],
        'expected': [
            {
                'town': 'Москва',
                'p50': 10.,
                'p75': 10.,
                'p99': 10.
            }
        ]
    },

    # Пустая выгрузка.
    # Обработчик не должен падать на пустой выгрузке.
    {
        'citizens': [],
        'expected': []
    },
]


@patch('analyzer.api.handlers.TownAgeStatView.CURRENT_DATE', new=CURRENT_DATE)
@pytest.mark.parametrize('dataset', datasets)
async def test_get_ages(api_client, dataset):
    # Перед прогоном каждого теста добавим в БД дополнительную выгрузку с
    # жителем из другого города, чтобы убедиться, что обработчик различает
    # жителей разных выгрузок.
    await import_data(api_client, [
        generate_citizen(citizen_id=1, town='Санкт-Петербург')
    ])

    import_id = await import_data(api_client, dataset['citizens'])
    result = await get_citizens_ages(api_client, import_id)

    assert len(dataset['expected']) == len(result), 'Towns number is different'
    actual_towns_map = {town['town']: town for town in result}

    for town in dataset['expected']:
        assert town['town'] in actual_towns_map
        actual_town = actual_towns_map[town['town']]

        for percentile in ['p50', 'p75', 'p99']:
            assert town[percentile] == actual_town[percentile], (
                f"{town['town']} {percentile} {actual_town[percentile]} does "
                f"not match expected value {town[percentile]}"
            )


async def test_get_nonexistent_import_birthdays(api_client):
    await get_citizens_ages(api_client, 999, HTTPStatus.NOT_FOUND)
