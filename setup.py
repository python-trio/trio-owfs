from setuptools import setup, find_packages

exec(open("trio_owfs/_version.py", encoding="utf-8").read())

LONG_DESC = """\
This library allows you to access 1wire buses with Python, using any
async library (trio, asyncio, curio).

This code does *not* try to talk to any 1wire interface by itself; it
uses TCP port 4304 (by default) to access one or more ``owserver``\ s.

Bus enumeration (when starting up, plus periodically in the background
if desired) is automatic and can be turned off.

This code supports background polling, alerts, and simultaneous
conversions. Bus couplers (DS2509) are handled transparently. Accessors to
device attributes are created from device descriptors, read from
``owserver`` and augmented by device-specific classes when necessary.

The name of this library is (a) historic, (b) its main author strongly
prefers Trio.
"""

setup(
    name="trio-owfs",
    version=__version__,  # noqa: W291,F821
    description="Async access to 1wire (asyncio,trio,curio)",
    url="https://github.com/python-trio/trio-owfs",
    long_description=LONG_DESC,
    author="Matthias Urlichs",
    author_email="matthias@urlichs.de",
    license="MIT -or- Apache License 2.0",
    packages=find_packages(),
    install_requires=[
        "anyio",
    ],
    keywords=[
        "trio",
        "async",
        "io",
        "networking",
    ],
    python_requires=">=3.5.3",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Framework :: AsyncIO",
        "Framework :: Trio",
    ],
)
