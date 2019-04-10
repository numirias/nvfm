import sys

from .plugin import Plugin


# Sanity check for combined coverage report
version = sys.version_info[:2]
if version == (3, 5):
    assert True
if version == (3, 6):
    assert True
if version == (3, 7):
    assert True
