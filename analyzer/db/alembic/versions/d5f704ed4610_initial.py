"""initial

Revision ID: d5f704ed4610
Revises:
Create Date: 2020-01-20 12:44:11.155956

"""
from alembic import op
from sqlalchemy import (
    Column, Date, Enum, ForeignKeyConstraint, Integer, PrimaryKeyConstraint,
    String,
)


# revision identifiers, used by Alembic.
revision = 'd5f704ed4610'
down_revision = None
branch_labels = None
depends_on = None


GenderType = Enum('female', 'male', name='gender')


def upgrade():
    op.create_table(
        'imports',
        Column('import_id', Integer(), nullable=False),
        PrimaryKeyConstraint('import_id', name=op.f('pk__imports'))
    )
    op.create_table(
        'citizens',
        Column('import_id', Integer(), nullable=False),
        Column('citizen_id', Integer(), nullable=False),
        Column('town', String(), nullable=False),
        Column('street', String(), nullable=False),
        Column('building', String(), nullable=False),
        Column('apartment', Integer(), nullable=False),
        Column('name', String(), nullable=False),
        Column('birth_date', Date(), nullable=False),
        Column('gender', GenderType, nullable=False),
        PrimaryKeyConstraint('import_id', 'citizen_id',
                             name=op.f('pk__citizens')),
        ForeignKeyConstraint(('import_id', ), ['imports.import_id'],
                             name=op.f('fk__citizens__import_id__imports'))
    )
    op.create_index(op.f('ix__citizens__town'), 'citizens', ['town'],
                    unique=False)

    op.create_table(
        'relations',
        Column('import_id', Integer(), nullable=False),
        Column('citizen_id', Integer(), nullable=False),
        Column('relative_id', Integer(), nullable=False),
        PrimaryKeyConstraint('import_id', 'citizen_id', 'relative_id',
                             name=op.f('pk__relations')),
        ForeignKeyConstraint(
            ('import_id', 'citizen_id'),
            ['citizens.import_id', 'citizens.citizen_id'],
            name=op.f('fk__relations__import_id_citizen_id__citizens')
        ),
        ForeignKeyConstraint(
            ('import_id', 'relative_id'),
            ['citizens.import_id', 'citizens.citizen_id'],
            name=op.f('fk__relations__import_id_relative_id__citizens')
        )
    )


def downgrade():
    op.drop_table('relations')
    op.drop_table('citizens')
    op.drop_table('imports')
    GenderType.drop(op.get_bind(), checkfirst=False)
