from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_urldispatcher import View
from asyncpgsa import PG
from sqlalchemy import exists, select

from analyzer.db.schema import imports_table


class BaseView(View):
    URL_PATH: str

    @property
    def pg(self) -> PG:
        return self.request.app['pg']


class BaseImportView(BaseView):
    @property
    def import_id(self):
        return int(self.request.match_info.get('import_id'))

    async def check_import_exists(self):
        query = select([
            exists().where(imports_table.c.import_id == self.import_id)
        ])
        if not await self.pg.fetchval(query):
            raise HTTPNotFound()
