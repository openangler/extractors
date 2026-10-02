"""_common.py — NC's binding of the shared extractor helpers.

The manifest contract and output-path handling live in shared/manifest.py,
shared by every state. This module re-exports them and binds what is NC's own:
the historical default output directory, kept so existing runs do not break.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))

import manifest                                         # noqa: E402
from manifest import *                                  # noqa: E402,F401,F403

STATE = "US-NC"
DEFAULT_OUT = "~/onedrive/fishing/nc-fishing-guide-data"


def add_out_arg(parser):
    return manifest.add_out_arg(parser, DEFAULT_OUT)


def resolve_out(cli_value=None):
    """--out wins, then $OPENANGLER_OUT, then the historical default path."""
    return manifest.resolve_out(cli_value, DEFAULT_OUT)
