import asyncio
import json
from asyncio import StreamReader, StreamWriter
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Self


class Connection:
    DIGITS_OF_ENCODED_DATA_LENGTH = 4

    def __init__(self, reader: StreamReader, writer: StreamWriter):
        self.reader = reader
        self.writer = writer

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.aclose()

    @classmethod
    async def start_server(cls, callback: Callable[[Self], Awaitable[None]], host: str) -> asyncio.Server:
        return await asyncio.start_server(cls._asyncio_callback(callback), host, 0)

    @classmethod
    def _asyncio_callback(
        cls,
        func: Callable[[Self], Awaitable[None]],
    ) -> Callable[[StreamReader, StreamWriter], Awaitable[None]]:
        @wraps(func)
        async def _callback(reader: StreamReader, writer: StreamWriter) -> None:
            async with cls(reader, writer) as connection:
                await func(connection)

        return _callback

    @staticmethod
    def port_of(server: asyncio.Server) -> int:
        return server.sockets[0].getsockname()[1]

    @classmethod
    @asynccontextmanager
    async def connect(cls, host: str, port: int) -> AsyncGenerator[Self]:
        reader, writer = await asyncio.open_connection(host, port)

        async with cls(reader, writer) as connection:
            yield connection

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
