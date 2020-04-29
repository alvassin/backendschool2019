from enum import EnumMeta
from http import HTTPStatus
from random import choice, randint, randrange, shuffle
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

import faker
from aiohttp.test_utils import TestClient
from aiohttp.typedefs import StrOrURL
from aiohttp.web_urldispatcher import DynamicResource

from analyzer.api.handlers import (
    CitizenBirthdaysView, CitizensView, CitizenView, ImportsView,
    TownAgeStatView,
)
from analyzer.api.schema import (
    BIRTH_DATE_FORMAT, CitizenPresentsResponseSchema, CitizensResponseSchema,
    ImportResponseSchema, PatchCitizenResponseSchema,
    TownAgeStatResponseSchema,
)
from analyzer.utils.pg import MAX_INTEGER


fake = faker.Faker('ru_RU')


def url_for(path: str, **kwargs) -> str:
    """
    Генерирует URL для динамического aiohttp маршрута с параметрами.
    """
    kwargs = {
        key: str(value)  # Все значения должны быть str (для DynamicResource)
        for key, value in kwargs.items()
    }
    return str(DynamicResource(path).url_for(**kwargs))


def generate_citizen(
        citizen_id: Optional[int] = None,
        name: Optional[str] = None,
        birth_date: Optional[str] = None,
        gender: Optional[str] = None,
        town: Optional[str] = None,
        street: Optional[str] = None,
        building: Optional[str] = None,
        apartment: Optional[int] = None,
        relatives: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Создает и возвращает жителя, автоматически генерируя данные для не
    указанных полей.
    """
    if citizen_id is None:
        citizen_id = randint(0, MAX_INTEGER)

    if gender is None:
        gender = choice(('female', 'male'))

    if name is None:
        name = fake.name_female() if gender == 'female' else fake.name_male()

    if birth_date is None:
        birth_date = fake.date_of_birth(
            minimum_age=0, maximum_age=80
        ).strftime(BIRTH_DATE_FORMAT)

    if town is None:
        town = fake.city_name()

    if street is None:
        street = fake.street_name()

    if building is None:
        building = str(randrange(1, 100))

    if apartment is None:
        apartment = randrange(1, 120)

    if relatives is None:
        relatives = []

    return {
        'citizen_id': citizen_id,
        'name': name,
        'birth_date': birth_date,
        'gender': gender,
        'town': town,
        'street': street,
        'building': building,
        'apartment': apartment,
        'relatives': relatives,
    }


def generate_citizens(
        citizens_num: int,
        relations_num: Optional[int] = None,
        unique_towns: int = 20,
        start_citizen_id: int = 0,
        **citizen_kwargs
) -> List[Dict[str, Any]]:
    """
    Генерирует список жителей.

    :param citizens_num: Количество жителей
    :param relations_num: Количество родственных связей (подразумевается одна
            связь между двумя людьми)
    :param unique_towns: Кол-во уникальных городов в выгрузке
    :param start_citizen_id: С какого citizen_id начинать
    :param citizen_kwargs: Аргументы для функции generate_citizen
    """
    # Ограничнный набор городов
    towns = [fake.city_name() for _ in range(unique_towns)]

    # Создаем жителей
    max_citizen_id = start_citizen_id + citizens_num - 1
    citizens = {}
    for citizen_id in range(start_citizen_id, max_citizen_id + 1):
        citizen_kwargs['town'] = citizen_kwargs.get('town', choice(towns))
        citizens[citizen_id] = generate_citizen(citizen_id=citizen_id,
                                                **citizen_kwargs)

    # Создаем родственные связи
    unassigned_relatives = relations_num or citizens_num // 10
    shuffled_citizen_ids = list(citizens.keys())
    while unassigned_relatives:
        # Перемешиваем список жителей
        shuffle(shuffled_citizen_ids)

        # Выбираем жителя, кому ищем родственника
        citizen_id = shuffled_citizen_ids[0]

        # Выбираем родственника для этого жителя и проставляем
        # двустороннюю связь
        for relative_id in shuffled_citizen_ids[1:]:
            if relative_id not in citizens[citizen_id]['relatives']:
                citizens[citizen_id]['relatives'].append(relative_id)
                citizens[relative_id]['relatives'].append(citizen_id)
                break
        else:
            raise ValueError('Unable to choose relative for citizen')
        unassigned_relatives -= 1

    return list(citizens.values())


def normalize_citizen(citizen):
    """
    Преобразует объект с жителем для сравнения с другими.
    """
    return {**citizen, 'relatives': sorted(citizen['relatives'])}


def compare_citizens(left: Mapping, right: Mapping) -> bool:
    return normalize_citizen(left) == normalize_citizen(right)


def compare_citizen_groups(left: Iterable, right: Iterable) -> bool:
    left = [normalize_citizen(citizen) for citizen in left]
    left.sort(key=lambda citizen: citizen['citizen_id'])

    right = [normalize_citizen(citizen) for citizen in right]
    right.sort(key=lambda citizen: citizen['citizen_id'])
    return left == right


async def import_data(
        client: TestClient,
        citizens: List[Mapping[str, Any]],
        expected_status: Union[int, EnumMeta] = HTTPStatus.CREATED,
        **request_kwargs
) -> Optional[int]:
    response = await client.post(
        ImportsView.URL_PATH, json={'citizens': citizens}, **request_kwargs
    )
    assert response.status == expected_status

    if response.status == HTTPStatus.CREATED:
        data = await response.json()
        errors = ImportResponseSchema().validate(data)
        assert errors == {}
        return data['data']['import_id']


async def get_citizens(
        client: TestClient,
        import_id: int,
        expected_status: Union[int, EnumMeta] = HTTPStatus.OK,
        **request_kwargs
) -> List[dict]:
    response = await client.get(
        url_for(CitizensView.URL_PATH, import_id=import_id),
        **request_kwargs
    )
    assert response.status == expected_status

    if response.status == HTTPStatus.OK:
        data = await response.json()
        errors = CitizensResponseSchema().validate(data)
        assert errors == {}
        return data['data']


async def patch_citizen(
        client: TestClient,
        import_id: int,
        citizen_id: int,
        data: Mapping[str, Any],
        expected_status: Union[int, EnumMeta] = HTTPStatus.OK,
        str_or_url: StrOrURL = CitizenView.URL_PATH,
        **request_kwargs
):
    response = await client.patch(
        url_for(str_or_url, import_id=import_id,
                citizen_id=citizen_id),
        json=data,
        **request_kwargs
    )
    assert response.status == expected_status
    if response.status == HTTPStatus.OK:
        data = await response.json()
        errors = PatchCitizenResponseSchema().validate(data)
        assert errors == {}
        return data['data']


async def get_citizens_birthdays(
        client: TestClient,
        import_id: int,
        expected_status: Union[int, EnumMeta] = HTTPStatus.OK,
        **request_kwargs
):
    response = await client.get(
        url_for(CitizenBirthdaysView.URL_PATH, import_id=import_id),
        **request_kwargs
    )
    assert response.status == expected_status
    if response.status == HTTPStatus.OK:
        data = await response.json()
        errors = CitizenPresentsResponseSchema().validate(data)
        assert errors == {}
        return data['data']


async def get_citizens_ages(
        client: TestClient,
        import_id: int,
        expected_status: Union[int, EnumMeta] = HTTPStatus.OK,
        **request_kwargs
):
    response = await client.get(
        url_for(TownAgeStatView.URL_PATH, import_id=import_id),
        **request_kwargs
    )
    assert response.status == expected_status
    if response.status == HTTPStatus.OK:
        data = await response.json()
        errors = TownAgeStatResponseSchema().validate(data)
        assert errors == {}
        return data['data']
