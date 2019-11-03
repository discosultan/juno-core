import logging
import sqlite3
from collections import defaultdict
from contextlib import asynccontextmanager
from decimal import Decimal
# TODO: mypy fails to recognise stdlib attributes get_args, get_origin. remove ignore when fixed
from typing import (  # type: ignore
    Any,
    AsyncIterable,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints
)

from aiosqlite import Connection, connect

import juno.json as json
from juno.time import strfspan, time_ms
from juno.utils import home_path

from .storage import Storage

_log = logging.getLogger(__name__)

# Version should be incremented every time a storage schema changes.
_VERSION = 13

T = TypeVar('T')

Key = Union[str, Tuple[Any, ...]]
Primitive = Union[bool, int, float, Decimal, str]


def _serialize_decimal(d: Decimal) -> bytes:
    return str(d).encode('ascii')


def _deserialize_decimal(s: bytes) -> Decimal:
    return Decimal(s.decode('ascii'))


sqlite3.register_adapter(Decimal, _serialize_decimal)
sqlite3.register_converter('DECIMAL', _deserialize_decimal)

sqlite3.register_adapter(bool, int)
sqlite3.register_converter('BOOLEAN', lambda v: bool(int(v)))


class SQLite(Storage):
    def __init__(self) -> None:
        self._tables: Dict[Any, Set[str]] = defaultdict(set)

    async def stream_object_spans(self, key: Key, type: Type[T], start: int,
                                  end: int) -> AsyncIterable[Tuple[int, int]]:
        _log.info(
            f'streaming {type.__name__} span(s) between {strfspan(start, end)} from {key} db'
        )
        async with self._connect(key) as db:
            span_table_name = f'{type.__name__}{Span.__name__}'
            await self._ensure_table(db, Span, span_table_name)
            query = f'SELECT * FROM {span_table_name} WHERE start < ? AND end > ? ORDER BY start'
            async with db.execute(query, [end, start]) as cursor:
                async for span_start, span_end in cursor:
                    yield max(span_start, start), min(span_end, end)

    async def stream_objects(self, key: Key, type: Type[T], start: int,
                             end: int) -> AsyncIterable[T]:
        PAGE_SIZE = 1000
        _log.info(f'streaming {type.__name__}(s) between {strfspan(start, end)} from {key} db')
        async with self._connect(key) as db:
            await self._ensure_table(db, type)
            query = f'SELECT * FROM {type.__name__} WHERE time >= ? AND time < ? ORDER BY time'
            async with db.execute(query, [start, end]) as cursor:
                while True:
                    rows = await cursor.fetchmany(PAGE_SIZE)
                    for row in rows:
                        yield type(*row)
                    if len(rows) < PAGE_SIZE:
                        break

    async def store_objects_and_span(
        self, key: Key, type: Type[Any], objects: List[Any], start: int, end: int
    ) -> None:
        if start > objects[0].time or end <= objects[-1].time:
            raise ValueError('Invalid input')

        _log.info(
            f'storing {len(objects)} {type.__name__}(s) between {strfspan(start, end)} to {key} db'
        )
        async with self._connect(key) as db:
            await self._ensure_table(db, type)
            try:
                await db.executemany(
                    f"INSERT INTO {type.__name__} "
                    f"VALUES ({', '.join(['?'] * len(get_type_hints(type)))})", objects
                )
            except sqlite3.IntegrityError as err:
                # TODO: Can we relax this constraint?
                _log.error(f'{err} {key}')
                raise
            span_table_name = f'{type.__name__}{Span.__name__}'
            await self._ensure_table(db, Span, span_table_name)
            await db.execute(f'INSERT INTO {span_table_name} VALUES (?, ?)', [start, end])
            await db.commit()

    async def get(self, key: Key, type_: Type[T]) -> Tuple[Optional[T], Optional[int]]:
        _log.info(f'getting value of type {type_.__name__} from {key} db')
        async with self._connect(key) as db:
            await self._ensure_table(db, Bag)
            cursor = await db.execute(
                f'SELECT * FROM {Bag.__name__} WHERE key=?', [type_.__name__]
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                return _load_type_from_string(type_, json.loads(row[1])), row[2]
            else:
                return None, None

    async def set(self, key: Key, type_: Type[T], item: T) -> None:
        _log.info(f'setting value of type {type_.__name__} to {key} db')
        async with self._connect(key) as db:
            await self._ensure_table(db, Bag)
            await db.execute(
                f'INSERT OR REPLACE INTO {Bag.__name__} VALUES (?, ?, ?)',
                [type_.__name__, json.dumps(item), time_ms()]
            )
            await db.commit()

    async def get_map(self, key: Key,
                      type_: Type[T]) -> Tuple[Optional[Dict[str, T]], Optional[int]]:
        _log.info(f'getting map of items of type {type_.__name__} from {key} db')
        async with self._connect(key) as db:
            await self._ensure_table(db, Bag)
            cursor = await db.execute(
                f'SELECT * FROM {Bag.__name__} WHERE key=?', ['map_' + type_.__name__]
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                return {
                    k: _load_type_from_string(type_, v)
                    for k, v in json.loads(row[1]).items()
                }, row[2]
            else:
                return None, None

    # TODO: Generic type
    async def set_map(self, key: Key, type_: Type[T], items: Dict[str, T]) -> None:
        _log.info(f'setting map of {len(items)} items of type  {type_.__name__} to {key} db')
        async with self._connect(key) as db:
            await self._ensure_table(db, Bag)
            await db.execute(
                f'INSERT OR REPLACE INTO {Bag.__name__} VALUES (?, ?, ?)',
                ['map_' + type_.__name__, json.dumps(items),
                 time_ms()]
            )
            await db.commit()

    @asynccontextmanager
    async def _connect(self, key: Key) -> AsyncIterator[Connection]:
        name = self._normalize_key(key)
        name = str(home_path('data') / f'v{_VERSION}_{name}.db')
        _log.debug(f'opening {name}')
        async with connect(name, detect_types=sqlite3.PARSE_DECLTYPES) as db:
            yield db

    async def _ensure_table(self, db: Any, type_: Type[Any], name: Optional[str] = None) -> None:
        if name is None:
            name = type_.__name__
        tables = self._tables[db]
        if name not in tables:
            await _create_table(db, type_, name)
            await db.commit()
            tables.add(name)

    def _normalize_key(self, key: Key) -> str:
        key_type = type(key)
        if key_type is str:
            return cast(str, key)
        elif key_type is tuple:
            return '_'.join(map(str, key))
        else:
            raise NotImplementedError()


async def _create_table(db: Any, type_: Type[Any], name: str) -> None:
    annotations = get_type_hints(type_)
    col_names = list(annotations.keys())
    col_types = [_type_to_sql_type(t) for t in annotations.values()]
    cols = []
    for i in range(0, len(col_names)):
        col_constrain = 'PRIMARY KEY' if i == 0 else 'NOT NULL'
        cols.append(f'{col_names[i]} {col_types[i]} {col_constrain}')
    await db.execute(f'CREATE TABLE IF NOT EXISTS {name} ({", ".join(cols)})')

    # TODO: Use typing instead based on NewType()?
    VIEW_COL_NAMES = ['time', 'start', 'end']
    if any((n for n in col_names if n in VIEW_COL_NAMES)):
        view_cols = []
        for col in col_names:
            if col in VIEW_COL_NAMES:
                view_cols.append(
                    f"strftime('%Y-%m-%d %H:%M:%S', {col} / 1000, 'unixepoch') AS {col}"
                )
            else:
                view_cols.append(col)

        await db.execute(
            f'CREATE VIEW IF NOT EXISTS {name}View AS '
            f'SELECT {", ".join(view_cols)} FROM {name}'
        )


def _type_to_sql_type(type_: Type[Primitive]) -> str:
    if type_ is int:
        return 'INTEGER'
    if type_ is float:
        return 'REAL'
    if type_ is Decimal:
        return 'DECIMAL'
    if type_ is str:
        return 'TEXT'
    if type_ is bool:
        return 'BOOLEAN'
    raise NotImplementedError(f'Missing conversion for type {type_}')


def _load_type_from_string(type_: Type[Any], values: Dict[str, Any]) -> Any:
    annotations = get_type_hints(type_)
    for key, attr_type in annotations.items():
        if get_origin(attr_type) is dict:
            sub_type = get_args(attr_type)[1]
            sub = values[key]
            for dk, dv in sub.items():
                sub[dk] = _load_type_from_string(sub_type, dv)
        elif _isnamedtuple(attr_type):
            # Materialize it.
            values[key] = _load_type_from_string(attr_type, values[key])
    return type_(**values)


def _isnamedtuple(type_: Type[Any]) -> bool:
    return issubclass(type_, tuple) and bool(getattr(type_, '_fields', False))


class Bag:
    key: str
    value: str
    time: int


class Span:
    start: int
    end: int
