"""_common.py — SC's binding of the shared extractor helpers.

Re-exports shared/manifest.py and binds what is SC's own. Unlike NC there is no
historical default output directory: an SC run must be told where to write
(`--out` or `$OPENANGLER_OUT`), and claim_state() refuses a directory that
already holds another state's dataset.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "shared"))

import manifest                                         # noqa: E402
from manifest import *                                  # noqa: E402,F401,F403

STATE = "US-SC"
DEFAULT_OUT = None


def add_out_arg(parser):
    return manifest.add_out_arg(parser, DEFAULT_OUT)


def resolve_out(cli_value=None):
    """--out wins, then $OPENANGLER_OUT; refuses another state's dataset."""
    out = manifest.resolve_out(cli_value, DEFAULT_OUT)
    manifest.claim_state(out, STATE)
    return out


def record_artifacts(out_dir, produced_by, artifacts, run=None):
    return manifest.record_artifacts(out_dir, produced_by, artifacts, run, state=STATE)
