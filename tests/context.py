"""Test support: put nc/ on sys.path and load fixtures.

The extractors are scripts, not an installed package, so tests import them the
same way the scripts import each other — with nc/ on sys.path.

Nothing in these tests touches the network. The fixtures are captured from a
produced NC dataset; the pipeline's four scraping steps are never run.
"""

import json
import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NC = os.path.join(ROOT, "nc")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

if NC not in sys.path:
    sys.path.insert(0, NC)


class _NoNetwork(socket.socket):
    """Fail loudly if a test ever reaches for a public agency endpoint."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "tests must not open sockets — these extractors scrape live public "
            "agency APIs; test the parsing against fixtures instead")


socket.socket = _NoNetwork


def fixture(name):
    """Load a fixture: .json is parsed, anything else is returned as text."""
    path = os.path.join(FIXTURES, name)
    with open(path, encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()
