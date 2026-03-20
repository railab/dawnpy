# tools/dawnpy/src/dawnpy/logger.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""The dawnpy logging module."""

import logging

logger = logging.getLogger("dawnpy")
# logging.basicConfig()

logger.propagate = True
logger.handlers = []
