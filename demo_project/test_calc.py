import pytest
from demo_project.calc import add, divide

def test_add():
    assert add(2, 3) == 5

def test_divide_ok():
    assert divide(10, 2) == 5

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        _ = divide(10, 0)
