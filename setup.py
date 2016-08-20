#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Distutil setup scripts for scriba and its requirements."""

# pylint: disable=import-error,no-name-in-module

__description__ = """The "scriba" writes out what POVs and Patches """ \
                  """we want to field, as a preparation for the """ \
                  """ambassador."""
__version__ = "0.0.1"

import os
import os.path
import shutil

from distutils.core import setup

with open('requirements.txt', 'r') as req_file:
    REQUIREMENTS = [r.strip() for r in req_file.readlines() if 'git' not in r]

setup(name='scriba',
      version=__version__,
      packages=['scriba', 'scriba.submitters'],
      install_requires=REQUIREMENTS,
      entry_points={
          'console_scripts': [
              "scriba=scriba.__main__:main"
          ],
      },
      description=__description__,
      url='https://github.com/mechaphish/scriba')
