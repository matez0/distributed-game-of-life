import json
from asyncio import StreamReader, StreamWriter
from typing import Any


class StreamSerializer:
    DIGITS_OF_ENCODED_DATA_LENGTH = 4

    @classmethod
    async def send(cls, writer: StreamWriter, data: Any) -> None:
        serialized_obj = json.dumps(data).encode()
        serialized_len = f"{len(serialized_obj):0{cls.DIGITS_OF_ENCODED_DATA_LENGTH}x}".encode()

        if len(serialized_len) != cls.DIGITS_OF_ENCODED_DATA_LENGTH:
            raise ValueError("Object to send has invalid length")

        writer.write(serialized_len)
        writer.write(serialized_obj)

        await writer.drain()

    @classmethod
    async def recv(cls, reader: StreamReader) -> Any:
        serialized_len = int((await reader.readexactly(cls.DIGITS_OF_ENCODED_DATA_LENGTH)), base=16)

        return json.loads(await reader.readexactly(serialized_len))
