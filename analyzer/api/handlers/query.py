from sqlalchemy import and_, func, select

from analyzer.db.schema import citizens_table, relations_table


CITIZENS_QUERY = select([
    citizens_table.c.citizen_id,
    citizens_table.c.name,
    citizens_table.c.birth_date,
    citizens_table.c.gender,
    citizens_table.c.town,
    citizens_table.c.street,
    citizens_table.c.building,
    citizens_table.c.apartment,
    # В результате LEFT JOIN у жителей не имеющих родственников список
    # relatives будет иметь значение [None]. Чтобы удалить это значение
    # из списка используется функция array_remove.
    func.array_remove(
        func.array_agg(relations_table.c.relative_id),
        None
    ).label('relatives')
]).select_from(
    citizens_table.outerjoin(
        relations_table, and_(
            citizens_table.c.import_id == relations_table.c.import_id,
            citizens_table.c.citizen_id == relations_table.c.citizen_id
        )
    )
).group_by(
    citizens_table.c.import_id,
    citizens_table.c.citizen_id
)
