from setuptools import setup, find_packages

exec(open("trio_owfs/_version.py", encoding="utf-8").read())

LONG_DESC = open("README.rst", encoding="utf-8").read()

setup(
    name="trio-owfs",
    version=__version__,  # noqa: W291,F821
    description="Access to 1wire",
    url="https://github.com/python-trio/trio-owfs",
    long_description=LONG_DESC,
    author="Matthias Urlichs",
    author_email="matthias@urlichs.de",
    license="MIT -or- Apache License 2.0",
    packages=find_packages(),
    install_requires=[
        "trio",
    ],
    keywords=[
        "trio",
        "async",
        "io",
        "networking",
    ],
    python_requires=">=3.6",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "License :: OSI Approved :: Apache Software License",
        "Framework :: Trio",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Framework :: Trio",
    ],
)
