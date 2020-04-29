"""
Модуль содержит схемы для валидации данных в запросах и ответах.

Схемы валидации запросов используются в бою для валидации данных отправленных
клиентами.

Схемы валидации ответов *ResponseSchema используются только при тестировании,
чтобы убедиться что обработчики возвращают данные в корректном формате.
"""
from datetime import date

from marshmallow import Schema, ValidationError, validates, validates_schema
from marshmallow.fields import Date, Dict, Float, Int, List, Nested, Str
from marshmallow.validate import Length, OneOf, Range

from analyzer.db.schema import Gender


BIRTH_DATE_FORMAT = '%d.%m.%Y'


class PatchCitizenSchema(Schema):
    name = Str(validate=Length(min=1, max=256))
    gender = Str(validate=OneOf([gender.value for gender in Gender]))
    birth_date = Date(format=BIRTH_DATE_FORMAT)
    town = Str(validate=Length(min=1, max=256))
    street = Str(validate=Length(min=1, max=256))
    building = Str(validate=Length(min=1, max=256))
    apartment = Int(validate=Range(min=0), strict=True)
    relatives = List(Int(validate=Range(min=0), strict=True))

    @validates('birth_date')
    def validate_birth_date(self, value: date):
        if value > date.today():
            raise ValidationError("Birth date can't be in future")

    @validates('relatives')
    def validate_relatives_unique(self, value: list):
        if len(value) != len(set(value)):
            raise ValidationError('relatives must be unique')


class CitizenSchema(PatchCitizenSchema):
    citizen_id = Int(validate=Range(min=0), strict=True, required=True)
    name = Str(validate=Length(min=1, max=256), required=True)
    gender = Str(validate=OneOf([gender.value for gender in Gender]),
                 required=True)
    birth_date = Date(format=BIRTH_DATE_FORMAT, required=True)
    town = Str(validate=Length(min=1, max=256), required=True)
    street = Str(validate=Length(min=1, max=256), required=True)
    building = Str(validate=Length(min=1, max=256), required=True)
    apartment = Int(validate=Range(min=0), strict=True, required=True)
    relatives = List(Int(validate=Range(min=0), strict=True), required=True)


class ImportSchema(Schema):
    citizens = Nested(CitizenSchema, many=True, required=True,
                      validate=Length(max=10000))

    @validates_schema
    def validate_unique_citizen_id(self, data, **_):
        citizen_ids = set()
        for citizen in data['citizens']:
            if citizen['citizen_id'] in citizen_ids:
                raise ValidationError(
                    'citizen_id %r is not unique' % citizen['citizen_id']
                )
            citizen_ids.add(citizen['citizen_id'])

    @validates_schema
    def validate_relatives(self, data, **_):
        relatives = {
            citizen['citizen_id']: set(citizen['relatives'])
            for citizen in data['citizens']
        }

        for citizen_id, relative_ids in relatives.items():
            for relative_id in relative_ids:
                if citizen_id not in relatives.get(relative_id, set()):
                    raise ValidationError(
                        f'citizen {relative_id} does not have '
                        f'relation with {citizen_id}'
                    )


class ImportIdSchema(Schema):
    import_id = Int(strict=True, required=True)


class ImportResponseSchema(Schema):
    data = Nested(ImportIdSchema(), required=True)


class CitizensResponseSchema(Schema):
    data = Nested(CitizenSchema(many=True), required=True)


class PatchCitizenResponseSchema(Schema):
    data = Nested(CitizenSchema(), required=True)


class PresentsSchema(Schema):
    citizen_id = Int(validate=Range(min=0), strict=True, required=True)
    presents = Int(validate=Range(min=0), strict=True, required=True)


# Схема, содержащая кол-во подарков, которое купят жители по месяцам.
# Чтобы не указывать вручную 12 полей класс можно сгенерировать.
CitizenPresentsByMonthSchema = type(
    'CitizenPresentsByMonthSchema', (Schema,),
    {
        str(i): Nested(PresentsSchema(many=True), required=True)
        for i in range(1, 13)
    }
)


class CitizenPresentsResponseSchema(Schema):
    data = Nested(CitizenPresentsByMonthSchema(), required=True)


class TownAgeStatSchema(Schema):
    town = Str(validate=Length(min=1, max=256), required=True)
    p50 = Float(validate=Range(min=0), required=True)
    p75 = Float(validate=Range(min=0), required=True)
    p99 = Float(validate=Range(min=0), required=True)


class TownAgeStatResponseSchema(Schema):
    data = Nested(TownAgeStatSchema(many=True), required=True)


class ErrorSchema(Schema):
    code = Str(required=True)
    message = Str(required=True)
    fields = Dict()


class ErrorResponseSchema(Schema):
    error = Nested(ErrorSchema(), required=True)
