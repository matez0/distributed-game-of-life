import asyncio
from asyncio import TaskGroup
from contextlib import aclosing, closing
from socket import socketpair
from unittest import IsolatedAsyncioTestCase

from dgol.stream import StreamSerializer


class TestStreamSerializer(IsolatedAsyncioTestCase):
    async def test_sent_data_can_be_received(self):
        sock_1, sock_2 = socketpair()
        _, writer = await asyncio.open_connection(sock=sock_1)
        reader, _writer = await asyncio.open_connection(sock=sock_2)

        data = 'data-to-send'

        with closing(writer), closing(_writer):
            async with TaskGroup() as task_group:
                receiver_task = task_group.create_task(StreamSerializer.recv(reader))
                task_group.create_task(StreamSerializer.send(writer, data))

            self.assertEqual(receiver_task.result(), data)

    async def test_error_when_sending_too_big_data(self):
        sock_1, sock_2 = socketpair()

        _, writer = await asyncio.open_connection(sock=sock_1)
        __, _writer = await asyncio.open_connection(sock=sock_2)

        with closing(writer), closing(_writer):
            with self.assertRaises(ValueError):
                await StreamSerializer.send(writer, 'd' * 0x10000)
