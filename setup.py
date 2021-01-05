#!/usr/bin/env python3

# Copyright Dansk Bibliotekscenter a/s. Licensed under GPLv3
# See license text in LICENSE.txt or at https://opensource.dbc.dk/licenses/gpl-3.0/

from setuptools import setup

setup(name="deployversioner",
    version="0.1.0",
    package_dir={"": "src"},
    packages=["deployversioner"],
    description="",
    provides=["deployversioner"],
    install_requires=["pyyaml", "requests"],
    entry_points=
        {"console_scripts": [
            "set-new-version = deployversioner.deployversioner:main"
        ]}
    )
