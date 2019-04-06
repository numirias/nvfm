import os
import re


def test_startup(vim):
    assert vim.options


def test_tabline(vim):
    tabline = vim.options['tabline']
    # Strip markup
    tabline = re.sub('%#.*?#', '', tabline)
    assert os.getcwd() in tabline
