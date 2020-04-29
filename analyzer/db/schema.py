from enum import Enum, unique

from sqlalchemy import (
    Column, Date, Enum as PgEnum, ForeignKey, ForeignKeyConstraint, Integer,
    MetaData, String, Table,
)


# SQLAlchemy рекомендует использовать единый формат для генерации названий для
# индексов и внешних ключей.
# https://docs.sqlalchemy.org/en/13/core/constraints.html#configuring-constraint-naming-conventions
convention = {
    'all_column_names': lambda constraint, table: '_'.join([
        column.name for column in constraint.columns.values()
    ]),
    'ix': 'ix__%(table_name)s__%(all_column_names)s',
    'uq': 'uq__%(table_name)s__%(all_column_names)s',
    'ck': 'ck__%(table_name)s__%(constraint_name)s',
    'fk': 'fk__%(table_name)s__%(all_column_names)s__%(referred_table_name)s',
    'pk': 'pk__%(table_name)s'
}

metadata = MetaData(naming_convention=convention)


@unique
class Gender(Enum):
    female = 'female'
    male = 'male'


imports_table = Table(
    'imports',
    metadata,
    Column('import_id', Integer, primary_key=True)
)

citizens_table = Table(
    'citizens',
    metadata,
    Column('import_id', Integer, ForeignKey('imports.import_id'),
           primary_key=True),
    Column('citizen_id', Integer, primary_key=True),
    Column('town', String, nullable=False, index=True),
    Column('street', String, nullable=False),
    Column('building', String, nullable=False),
    Column('apartment', Integer, nullable=False),
    Column('name', String, nullable=False),
    Column('birth_date', Date, nullable=False),
    Column('gender', PgEnum(Gender, name='gender'), nullable=False),
)

relations_table = Table(
    'relations',
    metadata,
    Column('import_id', Integer, primary_key=True),
    Column('citizen_id', Integer, primary_key=True),
    Column('relative_id', Integer, primary_key=True),
    ForeignKeyConstraint(
        ('import_id', 'citizen_id'),
        ('citizens.import_id', 'citizens.citizen_id')
    ),
    ForeignKeyConstraint(
        ('import_id', 'relative_id'),
        ('citizens.import_id', 'citizens.citizen_id')
    ),
)
