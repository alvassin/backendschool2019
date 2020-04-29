from http import HTTPStatus

from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_response import Response
from aiohttp_apispec import docs, request_schema, response_schema
from asyncpg import ForeignKeyViolationError
from marshmallow import ValidationError
from sqlalchemy import and_, or_

from analyzer.api.schema import PatchCitizenResponseSchema, PatchCitizenSchema
from analyzer.db.schema import citizens_table, relations_table

from .base import BaseImportView
from .query import CITIZENS_QUERY


class CitizenView(BaseImportView):
    URL_PATH = r'/imports/{import_id:\d+}/citizens/{citizen_id:\d+}'

    @property
    def citizen_id(self):
        return int(self.request.match_info.get('citizen_id'))

    @staticmethod
    async def acquire_lock(conn, import_id):
        await conn.execute('SELECT pg_advisory_xact_lock($1)', import_id)

    @staticmethod
    async def get_citizen(conn, import_id, citizen_id):
        query = CITIZENS_QUERY.where(and_(
            citizens_table.c.import_id == import_id,
            citizens_table.c.citizen_id == citizen_id
        ))
        return await conn.fetchrow(query)

    @staticmethod
    async def add_relatives(conn, import_id, citizen_id, relative_ids):
        if not relative_ids:
            return

        values = []
        base = {'import_id': import_id}
        for relative_id in relative_ids:
            values.append({**base, 'citizen_id': citizen_id,
                           'relative_id': relative_id})

            # Обратная связь не нужна, если житель сам себе родственник
            if citizen_id != relative_id:
                values.append({**base, 'citizen_id': relative_id,
                               'relative_id': citizen_id})
        query = relations_table.insert().values(values)

        try:
            await conn.execute(query)
        except ForeignKeyViolationError:
            raise ValidationError({'relatives': (
                f'Unable to add relatives {relative_ids}, some do not exist'
            )})

    @staticmethod
    async def remove_relatives(conn, import_id, citizen_id, relative_ids):
        if not relative_ids:
            return

        conditions = []
        for relative_id in relative_ids:
            conditions.extend([
                and_(relations_table.c.import_id == import_id,
                     relations_table.c.citizen_id == citizen_id,
                     relations_table.c.relative_id == relative_id),
                and_(relations_table.c.import_id == import_id,
                     relations_table.c.citizen_id == relative_id,
                     relations_table.c.relative_id == citizen_id)
            ])
        query = relations_table.delete().where(or_(*conditions))
        await conn.execute(query)

    @classmethod
    async def update_citizen(cls, conn, import_id, citizen_id, data):
        values = {k: v for k, v in data.items() if k != 'relatives'}
        if values:
            query = citizens_table.update().values(values).where(and_(
                citizens_table.c.import_id == import_id,
                citizens_table.c.citizen_id == citizen_id
            ))
            await conn.execute(query)

    @docs(summary='Обновить указанного жителя в определенной выгрузке')
    @request_schema(PatchCitizenSchema())
    @response_schema(PatchCitizenResponseSchema(), code=HTTPStatus.OK.value)
    async def patch(self):
        # Транзакция требуется чтобы в случае ошибки (или отключения клиента,
        # не дождавшегося ответа) откатить частично добавленные изменения, а
        # также для получения транзакционной advisory-блокировки.
        async with self.pg.transaction() as conn:

            # Блокировка позволит избежать состояние гонки между конкурентными
            # запросами на изменение родственников.
            await self.acquire_lock(conn, self.import_id)

            # Получаем информацию о жителе
            citizen = await self.get_citizen(conn, self.import_id,
                                             self.citizen_id)
            if not citizen:
                raise HTTPNotFound()

            # Обновляем таблицу citizens
            await self.update_citizen(conn, self.import_id, self.citizen_id,
                                      self.request['data'])

            # Обновляем родственные связи
            if 'relatives' in self.request['data']:
                cur_relatives = set(citizen['relatives'])
                new_relatives = set(self.request['data']['relatives'])
                await self.remove_relatives(
                    conn, self.import_id, self.citizen_id,
                    cur_relatives - new_relatives
                )
                await self.add_relatives(
                    conn, self.import_id, self.citizen_id,
                    new_relatives - cur_relatives
                )

            # Получаем актуальную информацию о
            citizen = await self.get_citizen(conn, self.import_id,
                                             self.citizen_id)
        return Response(body={'data': citizen})
