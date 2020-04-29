"""
Stairway-тест не требует поддержки и позволяет быстро и дешево находить
огромное количество распространенных типовых ошибок в миграциях:
- не реализованные методы downgrade,
- не удаленные типы данных в методах downgrade (например, enum),
- опечатки и другие ошибки.

Идея теста заключается в том, чтобы накатывать миграции по одной,
последовательно выполняя для каждой миграции методы upgrade, downgrade,
upgrade.

Подробнее про stairway тест можно посмотреть в записи доклада с Moscow
Python: https://bit.ly/3bpJ0gw
"""
from types import SimpleNamespace

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.script import Script, ScriptDirectory

from analyzer.utils.pg import make_alembic_config


def get_revisions():
    # Создаем объект с конфигурацей alembic (для получения списка миграций БД
    # не нужна).
    options = SimpleNamespace(config='alembic.ini', pg_url=None,
                              name='alembic', raiseerr=False, x=None)
    config = make_alembic_config(options)

    # Получаем директорию с миграциями alembic
    revisions_dir = ScriptDirectory.from_config(config)

    # Получаем миграции и сортируем в порядке от первой до последней
    revisions = list(revisions_dir.walk_revisions('base', 'heads'))
    revisions.reverse()
    return revisions


@pytest.mark.parametrize('revision', get_revisions())
def test_migrations_stairway(alembic_config: Config, revision: Script):
    upgrade(alembic_config, revision.revision)
    # -1 используется для downgrade первой миграции (т.к. ее down_revision
    # равен None)
    downgrade(alembic_config, revision.down_revision or '-1')
    upgrade(alembic_config, revision.revision)
