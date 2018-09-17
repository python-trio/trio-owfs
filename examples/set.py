"""walk.py -- a pyownet implementation of owget

This implementation is for python 2.X

This programs parses an owserver URI, constructed in the obvious way:
'owserver://hostname:port/path' and prints all nodes reachable below it.

The URI scheme 'owserver:' is optional. For 'hostname:port' the default
is 'localhost:4304'

Usage examples:

python walk.py //localhost:14304/
python walk.py //localhost:14304/26.000026D90200/
python walk.py -K //localhost:14304/26.000026D90200/temperature

Caution:
'owget.py //localhost:14304/26.000026D90200' or
'owget.py //localhost:14304/26.000026D90200/temperature/' yield an error

"""

from __future__ import print_function

import sys
import trio

import collections

import trio_click as click
from trio_owfs import OWFS

import logging
logger = logging.getLogger('examples.walk')

__all__ = ['main']

async def mon(ow, *, task_status=trio.TASK_STATUS_IGNORED):
    with ow.events as events:
        task_status.started()
        async for msg in events:
            logger.info("%s", msg)

@click.command()
@click.option('--host', default='localhost', help='host running owserver')
@click.option('--port', default=4304, type=int, help='owserver port')
@click.option('--debug', '-d', is_flag=True, help='Show debug information')
@click.argument('id')
@click.argument('attr')
@click.argument('data')
async def main(host, port, debug, id, attr, data):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    async with OWFS() as ow:
        if debug:
            await ow.add_task(mon, ow)
        s = await ow.add_server(host, port)
        dev = ow.get_device(id)
        if dev.bus is None:
            print("Device not found", file=sys.stderr)
        await dev.attr_set(attr, value=data)


if __name__ == '__main__':
    main()
