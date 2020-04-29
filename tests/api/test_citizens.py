from datetime import datetime
from http import HTTPStatus

import pytest

from analyzer.api.schema import BIRTH_DATE_FORMAT
from analyzer.db.schema import citizens_table, imports_table, relations_table
from analyzer.utils.testing import (
    compare_citizen_groups, generate_citizen, get_citizens,
)


datasets = [
    # Житель с несколькими родственниками.
    # Обработчик должен корректно возвращать жителя со всеми родственниками.
    [
        generate_citizen(citizen_id=1, relatives=[2, 3]),
        generate_citizen(citizen_id=2, relatives=[1]),
        generate_citizen(citizen_id=3, relatives=[1])
    ],

    # Житель без родственников.
    # Поле relatives должно содержать пустой список (может иметь значение
    # [null], которое появляется при агрегации строк с LEFT JOIN).
    [
        generate_citizen(relatives=[])
    ],

    # Выгрузка с жителем, который сам себе родственник.
    # Обработчик должен возвращать идентификатор жителя в списке родственников.
    [
        generate_citizen(citizen_id=1, name='Джейн', gender='male',
                         birth_date='17.02.2020', relatives=[1])
    ],

    # Пустая выгрузка.
    # Обработчик не должен падать на пустой выгрузке.
    [],
]


def import_dataset(connection, citizens) -> int:
    query = imports_table.insert().returning(imports_table.c.import_id)
    import_id = connection.execute(query).scalar()

    citizen_rows = []
    relations_rows = []
    for citizen in citizens:
        citizen_rows.append({
            'import_id': import_id,
            'citizen_id': citizen['citizen_id'],
            'name': citizen['name'],
            'birth_date': datetime.strptime(
                citizen['birth_date'], BIRTH_DATE_FORMAT
            ).date(),
            'gender': citizen['gender'],
            'town': citizen['town'],
            'street': citizen['street'],
            'building': citizen['building'],
            'apartment': citizen['apartment'],
        })

        for relative_id in citizen['relatives']:
            relations_rows.append({
                'import_id': import_id,
                'citizen_id': citizen['citizen_id'],
                'relative_id': relative_id,
            })

    if citizen_rows:
        query = citizens_table.insert().values(citizen_rows)
        connection.execute(query)

    if relations_rows:
        query = relations_table.insert().values(relations_rows)
        connection.execute(query)

    return import_id


@pytest.mark.parametrize('dataset', datasets)
async def test_get_citizens(api_client, migrated_postgres_connection, dataset):
    # Перед прогоном каждого теста добавляем в БД дополнительную выгрузку с
    # одним жителем, чтобы убедиться, что обработчик различает жителей разных
    # выгрузок.
    import_dataset(migrated_postgres_connection, [generate_citizen()])

    # Проверяем обработчик на указанных данных
    import_id = import_dataset(migrated_postgres_connection, dataset)
    actual_citizens = await get_citizens(api_client, import_id)
    assert compare_citizen_groups(actual_citizens, dataset)


async def test_get_non_existing_import(api_client):
    await get_citizens(api_client, 999, HTTPStatus.NOT_FOUND)
