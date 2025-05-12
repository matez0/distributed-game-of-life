import asyncio
from asyncio import TaskGroup
from contextlib import closing
from socket import socketpair
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from dgol.stream import StreamSerializer


class TestStreamSerializer(IsolatedAsyncioTestCase):
    async def test_sent_data_can_be_received(self):
        sock_1, sock_2 = socketpair()
        _reader, writer = await asyncio.open_connection(sock=sock_1)
        reader, _writer = await asyncio.open_connection(sock=sock_2)

        data = 'data-to-send'

        with closing(writer), closing(_writer):
            receiver = StreamSerializer(reader, _writer)
            sender = StreamSerializer(_reader, writer)

            async with TaskGroup() as task_group:
                receiver_task = task_group.create_task(receiver.recv())
                task_group.create_task(sender.send(data))

            self.assertEqual(receiver_task.result(), data)

    async def test_error_when_sending_too_big_data(self):
        sock_1, sock_2 = socketpair()

        _reader, writer = await asyncio.open_connection(sock=sock_1)
        _, _writer = await asyncio.open_connection(sock=sock_2)

        with closing(writer), closing(_writer):
            with self.assertRaises(ValueError):
                await StreamSerializer(_reader, writer).send('d' * 0x10000)

    async def test_callback_passes_an_instance_to_method_and_handles_closing(self):
        method_arg = Mock(value=None)

        class Example:
            @StreamSerializer.callback
            async def method(self, stream: StreamSerializer) -> None:
                method_arg.value = stream

        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)

        await Example().method(reader, writer)

        self.assertIsInstance(method_arg.value, StreamSerializer)

        writer.close.assert_called_once_with()
        writer.wait_closed.assert_awaited_once_with()

    async def test_can_communicate_with_a_server(self):
        class Server:
            @StreamSerializer.callback
            async def echo(self, stream):
                await stream.send(await stream.recv())

        host = "127.0.0.1"

        async with await asyncio.start_server(Server().echo, host, 0) as server:
            port = server.sockets[0].getsockname()[1]

            async with StreamSerializer.connect(host, port) as stream:
                data = "my-data"
                await stream.send(data)

                self.assertEqual(await stream.recv(), data)
