"""Run a bunch of URLs through the autoplot system."""

import os

import pytest
from iemweb.autoplot.autoplot import application
from werkzeug.test import Client


def get_test_urls():
    """yield a list of URLs to test."""
    listfn = os.path.join(os.path.dirname(__file__), "urllist.txt")
    with open(listfn) as fh:
        for line_in in fh:
            line = line_in.strip()
            if line == "" or line.startswith("#"):
                continue
            # Do apache rewrite magic here, example urllist entry
            # /plotting/auto/plot/199/opt:1::date:2024-07-24::_r:t::dpi:100.png
            line = line.replace("/plotting/auto/plot/", "")
            num, qstr = line.split("/", maxsplit=1)
            qstr, fmt = qstr.rsplit(".", 1)
            yield f"/?p={num}&q={qstr}&fmt={fmt}"


@pytest.mark.parametrize("url", get_test_urls())
def test_urls(url):
    """Run the test."""
    c = Client(application)
    res = c.get(url)
    assert res.status_code in [200, 400]
