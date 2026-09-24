import pytest
from calculator import add, sum_list, divide


def test_add():
    assert add(2, 3) == 5


def test_sum_list():
    # Should sum 1 + 2 + 3 + 4 = 10, but fails and returns 6
    assert sum_list([1, 2, 3, 4]) == 10


def test_divide():
    assert divide(10, 2) == 5
    with pytest.raises(ValueError):
        divide(5, 0)
