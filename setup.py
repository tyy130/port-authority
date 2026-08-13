#!/usr/bin/env python3
from pathlib import Path

from setuptools import setup, find_packages

long_description = (Path(__file__).parent / 'README.md').read_text()

setup(
    # PyPI rejects 'port-authority' as "too similar" to the existing
    # 'portauthority' package (name similarity is checked after stripping
    # hyphens/underscores/case). The importable module, CLI command names
    # (port-request, port-authority-daemon, ...), and GitHub repo are
    # unaffected -- this only changes what `pip install` needs.
    name='portauth',
    version='0.1.1',
    description='Centralized port allocation daemon — agents and scripts request a port instead of hardcoding or guessing one',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Tyler Hill',
    url='https://github.com/tyy130/port-authority',
    project_urls={
        'Source': 'https://github.com/tyy130/port-authority',
        'Bug Tracker': 'https://github.com/tyy130/port-authority/issues',
    },
    packages=find_packages(),
    scripts=['bin/port'],
    install_requires=[
        'requests>=2.28.0',
        'pyyaml>=6.0',
    ],
    extras_require={
        'mcp': ['mcp[cli]>=2.0.0'],
    },
    entry_points={
        'console_scripts': [
            'port-request=port_authority.cli:main',
            'port-authority-daemon=port_authority.daemon:run_daemon',
            'port-authority-mcp=port_authority.mcp_server:main',
        ],
    },
    # CI only tests 3.9-3.12 (mcp itself requires 3.10+) -- not claiming 3.8
    # support that's never been verified.
    python_requires='>=3.9',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
        'Environment :: Console',
        'Topic :: System :: Networking',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
