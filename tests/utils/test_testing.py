import pytest

from analyzer.utils.testing import generate_citizens


def test_generate_citizens():
    # Между двумя жителями может быть родственная связь
    generate_citizens(citizens_num=2, relations_num=1)

    # Между двумя жителями не может быть двух родственных связей
    with pytest.raises(ValueError):
        generate_citizens(citizens_num=2, relations_num=2)
