"""walk.py -- an AsyncOWFS implementation of owget

This programs connects to an owserver, enumerates all its nuses, and lists
the devices on it.

With ``-d device``, list that device's attributes. (You don't need the
complete path -- just the ID is sufficient.)

Usage examples:

python3 walk.py
python3 walk.py -d 05.67C6697351FF.BF

"""

from __future__ import print_function

import sys

import collections

import asyncclick as click
from asyncowfs import OWFS

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
@click.option('--device', '-d', help='List attributes of this device')
async def main(host, port, debug, device):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    async with OWFS() as ow:
        if debug:
            await ow.add_task(mon, ow)
        s = await ow.add_server(host, port)
        if device:
            device = device.rsplit('/',1)[-1]
            d = await ow.get_device(device)
            for f in d.fields:
                print(f)
        else:
            for b in s.all_buses:
                for d in b.devices:
                    p = '/'+'/'.join(d.bus.path)+'/'+d.id
                    print(p)

if __name__ == '__main__':
    main()
