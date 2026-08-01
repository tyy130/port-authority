#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='port-authority',
    version='0.1.0',
    description='Centralized port allocation system for managing ports across multiple projects',
    author='Tyler Hill',
    author_email='1forfunnn@gmail.com',
    url='https://github.com/tyy130/port-authority',
    packages=find_packages(),
    install_requires=[
        'requests>=2.28.0',
        'pyyaml>=6.0',
    ],
    entry_points={
        'console_scripts': [
            'port-request=port_authority.cli:main',
            'port-authority-daemon=port_authority.daemon:run_daemon',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
