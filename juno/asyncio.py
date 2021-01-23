import asyncio
import itertools
import logging
import os
import signal
import traceback
from dataclasses import dataclass, field
from typing import (
    Any, AsyncIterable, AsyncIterator, Callable, Coroutine, Generic, Iterable, Optional, TypeVar,
    cast
)

_log = logging.getLogger(__name__)

T = TypeVar('T')
U = TypeVar('U')


def resolved_future(result: T) -> asyncio.Future:
    future = asyncio.get_running_loop().create_future()
    future.set_result(result)
    return future


async def resolved_stream(*results: T) -> AsyncIterable[T]:
    for result in results:
        yield result


async def stream_with_timeout(
    async_iter: AsyncIterable[T], timeout: Optional[float]
) -> AsyncIterable[T]:
    iterator = async_iter.__aiter__()
    try:
        while True:
            yield await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
    except StopAsyncIteration:
        pass


async def repeat_async(value: T) -> AsyncIterable[T]:
    for val in itertools.repeat(value):
        yield val


async def chain_async(*async_iters: AsyncIterable[T]) -> AsyncIterable[T]:
    for async_iter in async_iters:
        async for val in async_iter:
            yield val


async def zip_async(
    async_iter1: AsyncIterable[T], async_iter2: AsyncIterable[U]
) -> AsyncIterable[tuple[T, U]]:
    iter1 = async_iter1.__aiter__()
    iter2 = async_iter2.__aiter__()
    while True:
        try:
            yield await asyncio.gather(iter1.__anext__(), iter2.__anext__())
        except StopAsyncIteration:
            break


async def enumerate_async(
    iterable: AsyncIterable[T], start: int = 0, step: int = 1
) -> AsyncIterable[tuple[int, T]]:
    i = start
    async for item in iterable:
        yield i, item
        i += step


async def list_async(async_iter: AsyncIterable[T]) -> list[T]:
    """Async equivalent to `list(iter)`."""
    return [item async for item in async_iter]


async def dict_async(async_iter: AsyncIterable[tuple[T, U]]) -> dict[T, U]:
    return {key: value async for key, value in async_iter}


async def first_async(async_iter: AsyncIterable[T]) -> T:
    async for item in async_iter:
        return item
    raise ValueError('First not found. No elements in sequence')


# Ref: https://stackoverflow.com/a/50903757/1466456
async def merge_async(*async_iters: AsyncIterable[T]) -> AsyncIterable[T]:
    iter_next: dict[AsyncIterator[T], Optional[asyncio.Future]] = {
        it.__aiter__(): None for it in async_iters
    }
    while iter_next:
        for it, it_next in iter_next.items():
            if it_next is None:
                fut = asyncio.ensure_future(it.__anext__())
                fut._orig_iter = it  # type: ignore
                iter_next[it] = fut
        done, _ = await asyncio.wait(iter_next.values(),  # type: ignore
                                     return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            iter_next[fut._orig_iter] = None  # type: ignore
            try:
                ret = fut.result()
            except StopAsyncIteration:
                del iter_next[fut._orig_iter]  # type: ignore
                continue
            yield ret


async def map_async(
    func: Callable[[T], U], async_iter: AsyncIterable[T]
) -> AsyncIterable[U]:
    async for item in async_iter:
        yield func(item)


async def cancel(*tasks: Optional[asyncio.Task]) -> None:
    await asyncio.gather(*(_cancel(t) for t in tasks if t))


async def _cancel(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        qualname = task.get_coro().__qualname__
        _log.info(f'{qualname} task cancelled')


def create_task_sigint_on_exception(coro: Coroutine) -> asyncio.Task:
    """ Creates a new task.
        Sends a SIGINT on unhandled exception.
    """

    def callback(task: asyncio.Task) -> None:
        task_name = task.get_coro().__qualname__
        if not task.cancelled() and (exc := task.exception()):
            msg = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            _log.error(f'unhandled exception in {task_name} task ({msg})')
            os.kill(os.getpid(), signal.SIGINT)

    child_task = asyncio.create_task(coro)
    child_task.add_done_callback(callback)
    return child_task


def create_task_cancel_owner_on_exception(coro: Coroutine) -> asyncio.Task:
    """ Creates a new task.
        Cancels the parent task in case the child task raises an unhandled exception.
    """
    parent_task = asyncio.current_task()

    def callback(task):
        task_name = task.get_coro().__qualname__
        if not task.cancelled() and (exc := task.exception()):
            if exc := task.exception():
                msg = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                _log.error(f'unhandled exception in {task_name} task ({msg})')
                # parent_task.set_exception(exc)  # Not allowed for a task.
                parent_task.cancel()

    child_task = asyncio.create_task(coro)
    child_task.add_done_callback(callback)
    return child_task


async def stream_queue(
    queue: asyncio.Queue, timeout: Optional[float] = None, raise_on_exc: bool = False
) -> AsyncIterable[Any]:
    if timeout is None:
        while True:
            item = await queue.get()
            if raise_on_exc and isinstance(item, Exception):
                raise item
            yield item
            queue.task_done()
    else:
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=timeout)
            if raise_on_exc and isinstance(item, Exception):
                raise item
            yield item
            queue.task_done()


class Barrier:
    def __init__(self, count: int) -> None:
        if count < 0:
            raise ValueError('Count cannot be negative')

        self._count = count
        self._event = asyncio.Event()
        self.clear()

    @property
    def locked(self) -> bool:
        return self._remaining_count > 0

    def clear(self) -> None:
        self._event.clear()
        self._remaining_count = self._count
        if not self.locked:
            self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def release(self) -> None:
        if self._remaining_count > 0:
            self._remaining_count -= 1
        else:
            raise ValueError('Barrier already unlocked')

        if not self.locked:
            self._event.set()


@dataclass
class _Slot:
    locked: bool = True
    cleared: asyncio.Event = field(default_factory=asyncio.Event)


class SlotBarrier(Generic[T]):
    def __init__(self, slots: Iterable[T]) -> None:
        self._slots = {s: _Slot() for s in set(slots)}
        self._event = asyncio.Event()
        self.clear()

    @property
    def locked(self) -> bool:
        return any(s.locked for s in self._slots.values())

    def slot_locked(self, slot: T) -> bool:
        return self._slots[slot].locked

    def clear(self) -> None:
        self._event.clear()
        for slot in self._slots.values():
            slot.locked = True
            slot.cleared.set()
        self._update_locked()

    async def wait(self) -> None:
        await self._event.wait()

    def release(self, slot: T) -> None:
        slot_ = self._slots.get(slot)

        if slot_ is None:
            raise ValueError(f'Slot {slot} does not exist')

        if slot_.locked:
            slot_.locked = False
        else:
            raise ValueError(f'Slot {slot} already released')

        self._update_locked()

    def add(self, slot: T) -> None:
        assert slot not in self._slots
        self._slots[slot] = _Slot()
        self._update_locked()

    def delete(self, slot: T) -> None:
        del self._slots[slot]
        self._update_locked()

    def _update_locked(self) -> None:
        if not self.locked:
            self._event.set()


class Event(Generic[T]):
    """Abstraction over `asyncio.Event` which adds additional capabilities:

    - passing data through set
    - autoclear after wait
    - timeout on wait"""
    def __init__(self, autoclear: bool = False) -> None:
        self._autoclear = autoclear
        self._event = asyncio.Event()
        self._event_data: Optional[T] = None

    async def wait(self, timeout: Optional[float] = None) -> T:
        if timeout is not None:
            await asyncio.wait_for(self._event.wait(), timeout)
        else:
            await self._event.wait()
        if self._autoclear:
            self.clear()
        # Ugly but we can't really express ourselves clearly to the type system.
        return cast(T, self._event_data)

    async def stream(self, timeout: Optional[float] = None) -> AsyncIterable[T]:
        while True:
            yield await self.wait(timeout)

    def set(self, data: Optional[T] = None) -> None:
        self._event_data = data
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()
