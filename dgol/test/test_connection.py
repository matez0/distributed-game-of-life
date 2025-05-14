import asyncio
from asyncio import TaskGroup
from contextlib import closing
from socket import socketpair
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from dgol.connection import Connection


class TestConnection(IsolatedAsyncioTestCase):
    async def test_sent_data_can_be_received(self):
        sock_1, sock_2 = socketpair()
        _reader, writer = await asyncio.open_connection(sock=sock_1)
        reader, _writer = await asyncio.open_connection(sock=sock_2)

        data = 'data-to-send'

        with closing(writer), closing(_writer):
            receiver = Connection(reader, _writer)
            sender = Connection(_reader, writer)

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
                await Connection(_reader, writer).send('d' * 0x10000)

    async def test_can_communicate_with_a_server(self):
        class Server:
            async def echo(self, connection):
                await connection.send(await connection.recv())

        host = "127.0.0.1"

        async with (
            await Connection.start_server(Server().echo, host) as server,
            Connection.connect(host, Connection.port_of(server)) as connection
        ):
            data = "my-data"
            await connection.send(data)

            self.assertEqual(await connection.recv(), data)
