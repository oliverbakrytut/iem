""".. title:: SPC Watch GeoJSON Service

Return to `API Services </api/#json>`_.

This service provides information about Storm Prediction Center (SPC) watches
for a given latitude and longitude point.

Changelog
---------

- 2024-07-09: Add csv and excel output formats

Example Requests
----------------

Return all watches that had a polygon coincident with the point at 41.9N, 93.6W

https://mesonet.agron.iastate.edu/json/spcwatch.py?lat=41.9&lon=-93.6

Return all watches that were valid at 2024-08-01 00 UTC, sorry that this uses
a lame format, will update to ISO8601 soon.

https://mesonet.agron.iastate.edu/json/spcwatch.py?ts=202408010000

Return the above, but in CSV format

https://mesonet.agron.iastate.edu/json/spcwatch.py?ts=202408010000&fmt=csv

And now excel

https://mesonet.agron.iastate.edu/json/spcwatch.py?ts=202408010000&fmt=excel

"""

from datetime import datetime, timezone
from io import BytesIO

import geopandas as gpd
from pydantic import Field
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.reference import ISO8601
from pyiem.util import utc
from pyiem.webutil import CGIModel, iemapp


class Schema(CGIModel):
    """See how we are called."""

    fmt: str = Field(
        default="geojson",
        description="The format to return data in, either json, excel, or csv",
        pattern="^(geojson|excel|csv)$",
    )
    ts: str = Field(
        None, description="The timestamp to query for", pattern="^[0-9]{12}$"
    )
    lat: float = Field(
        default=None,
        description="The latitude to query for",
    )
    lon: float = Field(
        default=None,
        description="The longitude to query for",
    )
    callback: str = Field(
        None, description="Callback function for JSONP output"
    )


def process_df(watches: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Common."""
    if not watches.empty:
        watches["year"] = watches["ii"].dt.year
        watches["spcurl"] = (
            "https://www.spc.noaa.gov/products/watch/"
            + watches["year"].astype(str)
            + "/ww"
            + watches["number"].apply(lambda x: f"{x:04.0f}")
            + ".html"
        )
        watches["issue"] = watches["ii"].dt.strftime(ISO8601)
        watches["expire"] = watches["ee"].dt.strftime(ISO8601)
    return watches.drop(columns=["ii", "ee"])


def pointquery(lon, lat) -> gpd.GeoDataFrame:
    """Do a query for stuff"""
    with get_sqlalchemy_conn("postgis") as conn:
        watches = gpd.read_postgis(
            sql_helper("""
        SELECT sel, issued at time zone 'UTC' as ii,
        expired at time zone 'UTC' as ee, type, geom, num as number,
        max_hail_size, max_wind_gust_knots, is_pds
        from watches where ST_Contains(geom, ST_Point(:lon, :lat, 4326))
        ORDER by issued DESC
        """),
            conn,
            params={"lon": lon, "lat": lat},
            geom_col="geom",
        )  # type: ignore
    return process_df(watches)


def dowork(valid) -> gpd.GeoDataFrame:
    """Actually do stuff"""
    with get_sqlalchemy_conn("postgis") as conn:
        watches = gpd.read_postgis(
            sql_helper("""
        SELECT sel, issued at time zone 'UTC' as ii,
        expired at time zone 'UTC' as ee, type, geom, num as number,
        max_hail_size, max_wind_gust_knots, is_pds
        from watches where issued <= :valid and expired > :valid
        """),
            conn,
            params={"valid": valid},
            geom_col="geom",
        )  # type: ignore
    return process_df(watches)


def get_ct(environ) -> str:
    """Figure out the content type."""
    fmt = environ["fmt"]
    if fmt == "geojson":
        return "application/vnd.geo+json"
    if fmt == "excel":
        return "application/vnd.ms-excel"
    return "text/csv"


@iemapp(content_type=get_ct, help=__doc__, schema=Schema)
def application(environ, start_response):
    """Answer request."""
    if environ["ts"] is None:
        ts = utc()
    else:
        ts = datetime.strptime(environ["ts"], "%Y%m%d%H%M")
    ts = ts.replace(tzinfo=timezone.utc)
    fmt = environ["fmt"]
    if environ["lon"] is not None and environ["lat"] is not None:
        watches = pointquery(environ["lon"], environ["lat"])
    else:
        watches = dowork(ts)

    if fmt == "geojson":
        headers = [("Content-type", "application/vnd.geo+json")]
        start_response("200 OK", headers)
        return watches.to_json()
    if fmt == "excel":
        headers = [
            ("Content-type", "application/vnd.ms-excel"),
            ("Content-Disposition", "attachment; filename=watches.xls"),
        ]
        start_response("200 OK", headers)
        with BytesIO() as bio:
            watches.drop(columns="geom").to_excel(bio, index=False)
            return bio.getvalue()

    headers = [
        ("Content-type", "text/csv"),
        ("Content-Disposition", "attachment; filename=watches.csv"),
    ]
    start_response("200 OK", headers)
    return watches.drop(columns="geom").to_csv(index=False).encode("ascii")
