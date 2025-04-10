"""
Download RTMA Rapid Updates grids

Run from RUN_50_AFTER.sh for previous hour
"""

import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

import click
import httpx
import pygrib
from pyiem.util import archive_fetch, exponential_backoff, logger, utc

LOG = logger()
ARCHIVE_THRES = utc() - timedelta(days=3)


def fetch_aws(dt: datetime):
    """Get the data via AWS PDS."""
    ppath = (
        f"{dt:%Y/%m/%d}/model/rtma/{dt:%H}/"
        f"rtma2p5_ru.t{dt:%H%M}z.2dvaranl_ndfd.grb2"
    )
    with archive_fetch(ppath) as fn:
        if fn is not None:
            LOG.info("Skipping as we have data %s", ppath)
            return

    b = "_" if dt > utc(2021, 9, 10) else "-"
    url = (
        f"https://s3.amazonaws.com/noaa-rtma-pds/rtma2p5{b}ru.{dt:%Y%m%d}/"
        f"rtma2p5_ru.t{dt:%H%M}z.2dvarges_ndfd.grb2"
    )
    req = exponential_backoff(httpx.get, url, timeout=30)
    if req is None or req.status_code != 200:
        LOG.info("failed to get idx: %s", url)
        return
    with tempfile.NamedTemporaryFile("wb", delete=False) as tmpfp:
        tmpfp.write(req.content)
    grbs = pygrib.open(tmpfp.name)
    with tempfile.NamedTemporaryFile("wb", delete=False) as tmpfp2:
        tmpfp2.write(grbs.select(name="2 metre temperature")[0].tostring())
        grbs.seek(0)
        tmpfp2.write(
            grbs.select(name="2 metre dewpoint temperature")[0].tostring()
        )
    cmd = [
        "pqinsert",
        "-i",
        "-p",
        (
            f"data a {dt:%Y%m%d%H%M} bogus model/rtma/"
            f"{dt:%H}/{ppath.split('/')[-1]} grib2"
        ),
        tmpfp2.name,
    ]
    LOG.info(" ".join(cmd))
    subprocess.call(cmd)

    os.unlink(tmpfp.name)
    os.unlink(tmpfp2.name)


def fetch(dt):
    """Fetch the data for this timestamp"""
    ppath = (
        f"{dt:%Y/%m/%d}/model/rtma/{dt:%H}/"
        f"rtma2p5_ru.t{dt:%H%M}z.2dvaranl_ndfd.grb2"
    )
    with archive_fetch(ppath) as fn:
        if fn is not None:
            LOG.info("Skipping as we have data %s", ppath)
            return
    uri = (
        "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtma/prod/"
        f"rtma2p5_ru.{dt:%Y%m%d}/rtma2p5_ru.t{dt:%H%M}z.2dvaranl_ndfd.grb2.idx"
    )
    req = exponential_backoff(httpx.get, uri, timeout=30)
    if req is None or req.status_code != 200:
        LOG.info("failed to get idx: %s", uri)
        return

    offsets = []
    neednext = False
    for line in req.content.decode("utf-8").split("\n"):
        tokens = line.split(":")
        if len(tokens) < 3:
            continue
        if neednext:
            offsets[-1].append(int(tokens[1]))
            neednext = False
        # Precip and high/low temp
        if tokens[3] in ["TMP", "DPT"]:
            offsets.append([int(tokens[1])])
            neednext = True

    if len(offsets) != 2:
        LOG.info("Failed to find required gribs")
        return

    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmpfp:
        for pr in offsets:
            headers = {"Range": f"bytes={pr[0]}-{pr[1]}"}
            req = exponential_backoff(
                httpx.get, uri[:-4], headers=headers, timeout=30
            )
            if req is None:
                LOG.warning("failure for uri: %s", uri)
                continue
            tmpfp.write(req.content)
    cmd = [
        "pqinsert",
        "-i",
        "-p",
        (
            f"data a {dt:%Y%m%d%H%M} bogus model/rtma/"
            f"{dt:%H}/{ppath.split('/')[-1]} grib2"
        ),
        tmpfp.name,
    ]
    LOG.info(" ".join(cmd))
    subprocess.call(cmd)
    os.unlink(tmpfp.name)


@click.command()
@click.option("--valid", required=True, type=click.DateTime(), help="UTC")
def main(valid: datetime):
    """Go Main Go"""
    valid = valid.replace(tzinfo=timezone.utc)

    # Backfilling mode
    for hroffset in [0, 6, 12, 24]:
        for minute in [0, 15, 30, 45]:
            ts = (valid - timedelta(hours=hroffset)).replace(minute=minute)
            (fetch if ts > ARCHIVE_THRES else fetch_aws)(ts)


if __name__ == "__main__":
    main()
