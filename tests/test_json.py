from decimal import Decimal

import pytest

import juno.json as json


class Complex:
    def __init__(self, value):
        self.value = value


@pytest.mark.parametrize('input,expected_output', [
    (Decimal('0.1'), '0.1'),
    (Complex(Complex('0.1')), '{"value": {"value": "0.1"}}'),
    ({'value': Decimal('0.1')}, '{"value": "0.1"}'),
    ([Decimal('0.1')], '["0.1"]'),
])
def test_dumps(input, expected_output):
    assert json.dumps(input) == expected_output


def test_dumps_complicated():
    input = {
        'foo': Decimal('0.1'),
        'bar': 'hello',
        'baz': 1,
        'qux': [1],
        'quux': {'corge': 1},
    }
    expected_output = '{"foo": "0.1", "bar": "hello", "baz": 1, "qux": [1], "quux": {"corge": 1}}'
    assert json.dumps(input) == expected_output


@pytest.mark.parametrize('input,expected_output', [
    ('0.1', Decimal('0.1')),
    ('{"value": "0.1"}', {'value': '0.1'}),
    ('["0.1"]', ['0.1']),
])
def test_loads(input, expected_output):
    assert json.loads(input) == expected_output