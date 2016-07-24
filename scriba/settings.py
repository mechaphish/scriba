#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Load settings from environment variables."""

from __future__ import absolute_import, unicode_literals

from os.path import join, dirname

# pylint: disable=import-error
from dotenv import load_dotenv
# pylint: enable=import-error

load_dotenv(join(dirname(__file__), '../.env'))
