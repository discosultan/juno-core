from decimal import Decimal
from typing import NamedTuple, _GenericAlias  # type: ignore

from juno import cffi


class Foo(NamedTuple):
    x: int
    y: Decimal


def test_build_struct():
    output = cffi.build_struct(Foo)
    assert output == '''typedef struct {
    uint32_t x;
    double y;
} Foo;
'''


def test_build_struct_exclude_field():
    output = cffi.build_struct(Foo, exclude=['x'])
    assert output == '''typedef struct {
    double y;
} Foo;
'''


def bar(x: int, y: Decimal) -> int:
    pass


def test_build_function():
    output = cffi.build_function(bar)
    assert output == '''uint32_t bar(
    uint32_t x,
    double y);
'''


def test_build_function_from_params():
    output = cffi.build_function_from_params('bar', int, ('x', int), ('y', Decimal))
    assert output == '''uint32_t bar(
    uint32_t x,
    double y);
'''


Baz = _GenericAlias(int, (), name='Baz')


def test_build_struct_custom_mapping():
    cffi.register_custom_mapping(Baz, 'uint64_t')
    output = cffi.build_function_from_params('baz', Baz, ('x', int), ('y', Baz))
    cffi.deregister_custom_mapping(Baz)
    assert output == '''uint64_t baz(
    uint32_t x,
    uint64_t y);
'''