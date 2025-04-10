"""Run a bunch of URLs through the autoplot system."""

import os

import pytest
from iemweb.autoplot.index import application
from werkzeug.test import Client


def get_test_urls():
    """yield a list of URLs to test."""
    listfn = os.path.join(os.path.dirname(__file__), "urllist_index.txt")
    with open(listfn) as fh:
        for line_in in fh:
            line = line_in.strip()
            if line == "" or line.startswith("#"):
                continue
            yield line


@pytest.mark.parametrize("url", get_test_urls())
def test_urls(url):
    """Run the test."""
    c = Client(application)
    res = c.get(url)
    assert res.status_code == 200


def test_cookie_set_to_all():
    """Test handling of when cookie is set to _ALL."""
    cl = Client(application)
    cl.set_cookie("station_WFO", "_ALL")
    res = cl.get("?q=72")
    assert res.status_code == 200
