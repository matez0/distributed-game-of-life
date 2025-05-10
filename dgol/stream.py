import asyncio
import json
from asyncio import StreamReader, StreamWriter
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Self


class StreamSerializer:
    DIGITS_OF_ENCODED_DATA_LENGTH = 4

    def __init__(self, reader: StreamReader, writer: StreamWriter):
        self.reader = reader
        self.writer = writer

    @classmethod
    def callback(
        cls,
        method: Callable[[Any, Self], Awaitable[None]],
    ) -> Callable[[Any, StreamReader, StreamWriter], Awaitable[None]]:
        @wraps(method)
        async def _callback(self: Any, reader: StreamReader, writer: StreamWriter) -> None:
            try:
                await method(self, cls(reader, writer))

            finally:
                writer.close()
                await writer.wait_closed()

        return _callback

    @classmethod
    @asynccontextmanager
    async def connect(cls, host: str, port: int) -> AsyncGenerator[Self]:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            yield cls(reader, writer)

        finally:
            writer.close()
            await writer.wait_closed()

    async def aclose(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()

    async def send(self, data: Any) -> None:
        serialized_obj = json.dumps(data).encode()
        serialized_len = f"{len(serialized_obj):0{self.DIGITS_OF_ENCODED_DATA_LENGTH}x}".encode()

        if len(serialized_len) != self.DIGITS_OF_ENCODED_DATA_LENGTH:
            raise ValueError("Object to send has invalid length")

        self.writer.write(serialized_len)
        self.writer.write(serialized_obj)

        await self.writer.drain()

    async def recv(self) -> Any:
        serialized_len = int((await self.reader.readexactly(self.DIGITS_OF_ENCODED_DATA_LENGTH)), base=16)

        return json.loads(await self.reader.readexactly(serialized_len))
