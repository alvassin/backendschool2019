import json
from datetime import date
from decimal import Decimal
from functools import partial, singledispatch
from typing import Any

from aiohttp.payload import JsonPayload as BaseJsonPayload, Payload
from aiohttp.typedefs import JSONEncoder
from asyncpg import Record

from analyzer.api.schema import BIRTH_DATE_FORMAT


@singledispatch
def convert(value):
    """
    Модуль json позволяет указать функцию, которая будет вызываться для
    обработки не сериализуемых в JSON объектов. Функция должна вернуть либо
    сериализуемое в JSON значение, либо исключение TypeError:
    https://docs.python.org/3/library/json.html#json.dump
    """
    raise TypeError(f'Unserializable value: {value!r}')


@convert.register(Record)
def convert_asyncpg_record(value: Record):
    """
    Позволяет автоматически сериализовать результаты запроса, возвращаемые
    asyncpg.
    """
    return dict(value)


@convert.register(date)
def convert_date(value: date):
    """
    В проекте объект date возвращается только в одном случае - если необходимо
    отобразить дату рождения. Для отображения даты рождения должен
    использоваться формат ДД.ММ.ГГГГ.
    """
    return value.strftime(BIRTH_DATE_FORMAT)


@convert.register(Decimal)
def convert_decimal(value: Decimal):
    """
    asyncpg возвращает округленные перцентили возвращаются виде экземпляров
    класса Decimal.
    """
    return float(value)


dumps = partial(json.dumps, default=convert, ensure_ascii=False)


class JsonPayload(BaseJsonPayload):
    """
    Заменяет функцию сериализации на более "умную" (умеющую упаковывать в JSON
    объекты asyncpg.Record и другие сущности).
    """
    def __init__(self,
                 value: Any,
                 encoding: str = 'utf-8',
                 content_type: str = 'application/json',
                 dumps: JSONEncoder = dumps,
                 *args: Any,
                 **kwargs: Any) -> None:
        super().__init__(value, encoding, content_type, dumps, *args, **kwargs)


class AsyncGenJSONListPayload(Payload):
    """
    Итерируется по объектам AsyncIterable, частями сериализует данные из них
    в JSON и отправляет клиенту.
    """
    def __init__(self, value, encoding: str = 'utf-8',
                 content_type: str = 'application/json',
                 root_object: str = 'data',
                 *args, **kwargs):
        self.root_object = root_object
        super().__init__(value, content_type=content_type, encoding=encoding,
                         *args, **kwargs)

    async def write(self, writer):
        # Начало объекта
        await writer.write(
            ('{"%s":[' % self.root_object).encode(self._encoding)
        )

        first = True
        async for row in self._value:
            # Перед первой строчкой запятая не нужнаа
            if not first:
                await writer.write(b',')
            else:
                first = False

            await writer.write(dumps(row).encode(self._encoding))

        # Конец объекта
        await writer.write(b']}')


__all__ = (
    'JsonPayload', 'AsyncGenJSONListPayload'
)
