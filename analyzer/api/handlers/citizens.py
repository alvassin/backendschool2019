from aiohttp.web_response import Response
from aiohttp_apispec import docs, response_schema

from analyzer.api.schema import CitizensResponseSchema
from analyzer.db.schema import citizens_table as citizens_t
from analyzer.utils.pg import SelectQuery

from .base import BaseImportView
from .query import CITIZENS_QUERY


class CitizensView(BaseImportView):
    URL_PATH = r'/imports/{import_id:\d+}/citizens'

    @docs(summary='Отобразить жителей для указанной выгрузки')
    @response_schema(CitizensResponseSchema())
    async def get(self):
        await self.check_import_exists()

        query = CITIZENS_QUERY.where(
            citizens_t.c.import_id == self.import_id
        )
        body = SelectQuery(query, self.pg.transaction())
        return Response(body=body)
