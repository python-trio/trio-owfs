"""get.py -- an AsyncOWFS implementation of owget

Usage example:

$ python3 get.py 05.67C6697351FF.BF PIO
1
"""

from __future__ import print_function

import sys

import collections

import asyncclick as click
from asyncowfs import OWFS
import asyncowfs.error as err

import logging
logger = logging.getLogger('examples.walk')

__all__ = ['main']

async def mon(ow):
    async with ow.events as events:
        async for msg in events:
            logger.info("%s", msg)

@click.command()
@click.option('--host', '-h', default='localhost', help='host running owserver')
@click.option('--port', '-p', default=4304, type=int, help='owserver port')
@click.option('--debug', '-D', is_flag=True, help='Show debug information')
@click.argument('id')
@click.argument('attr')
async def main(host, port, debug, id, attr):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    async with OWFS() as ow:
        if debug:
            await ow.add_task(mon, ow)
        s = await ow.add_server(host, port)
        attr = [k for k in attr.split('/') if k]
        dev = await ow.get_device(id)
        if dev.bus is None:
            print("Device not found", file=sys.stderr)
            sys.exit(1)

        print((await dev.attr_get(*attr)).decode("utf-8").strip())



if __name__ == '__main__':
    main()
