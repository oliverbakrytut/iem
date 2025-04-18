"""
This chart displays a simple time series of
an observed variable for a location of your choice.  For sites in the
US, the daily high and low temperature climatology is presented as a
filled bar for each day plotted when Air Temperature is selected.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import NoDataFound
from pyiem.plot import figure_axes

MDICT = {
    "tmpf": "Air Temperature",
    "dwpf": "Dew Point Temperature",
    "feel": "Feels Like Temperature",
    "alti": "Pressure Altimeter",
    "relh": "Relative Humidity",
    "mslp": "Sea Level Pressure",
}
UNITS = {
    "tmpf": "°F",
    "dwpf": "°F",
    "alti": "inch",
    "mslp": "mb",
    "feel": "°F",
    "relh": "%",
}


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {"description": __doc__, "data": True}
    ts = date.today() - timedelta(days=365)
    desc["arguments"] = [
        dict(
            type="zstation",
            name="zstation",
            default="AMW",
            network="IA_ASOS",
            label="Select Station:",
        ),
        dict(
            type="date",
            name="sdate",
            default=ts.strftime("%Y/%m/%d"),
            label="Start Date of Plot:",
            min="1951/01/01",
        ),  # Comes back to python as yyyy-mm-dd
        dict(type="int", name="days", default="365", label="Days to Plot"),
        dict(
            type="select",
            name="var",
            options=MDICT,
            default="tmpf",
            label="Variable to Plot",
        ),
    ]
    return desc


def get_highcharts(ctx: dict) -> dict:
    """Highcharts output"""
    add_ctx(ctx)
    ranges = []
    now = ctx["sdate"]
    oneday = timedelta(days=1)
    while ctx["climo"] and (now - oneday) <= ctx["edate"]:
        ranges.append(
            [
                int(now.strftime("%s")) * 1000.0,
                ctx["climo"][now.strftime("%m%d")]["low"],
                ctx["climo"][now.strftime("%m%d")]["high"],
            ]
        )
        now += oneday

    j = {}
    j["title"] = dict(text=f"{ctx['_sname']} Time Series")
    j["xAxis"] = dict(type="datetime")
    j["yAxis"] = dict(
        title=dict(text="%s %s" % (MDICT[ctx["var"]], UNITS[ctx["var"]]))
    )
    j["tooltip"] = {
        "crosshairs": True,
        "shared": True,
        "valueSuffix": f" {UNITS[ctx['var']]}",
    }
    j["legend"] = {}
    j["time"] = {"useUTC": False}
    j["exporting"] = {"enabled": True}
    j["chart"] = {"zoomType": "x"}
    j["plotOptions"] = {"line": {"turboThreshold": 0}}
    j["series"] = [
        {
            "name": MDICT[ctx["var"]],
            "data": list(
                zip(
                    ctx["df"].ticks.values.tolist(),
                    ctx["df"].datum.values.tolist(),
                    strict=True,
                )
            ),
            "zIndex": 2,
            "color": "#FF0000",
            "lineWidth": 2,
            "marker": {"enabled": False},
            "type": "line",
        }
    ]
    if ranges:
        j["series"].append(
            {
                "name": "Climo Hi/Lo Range",
                "data": ranges,
                "type": "arearange",
                "lineWidth": 0,
                "color": "#ADD8E6",
                "fillOpacity": 0.3,
                "zIndex": 0,
            }
        )
    if ctx["var"] in ["tmpf", "dwpf"]:
        j["yAxis"]["plotLines"] = [
            {
                "value": 32,
                "width": 2,
                "zIndex": 1,
                "color": "#000",
                "label": {"text": "32°F"},
            }
        ]

    return j


def add_ctx(ctx):
    """Get data common to both methods"""
    ctx["station"] = ctx["zstation"]
    sdate = ctx["sdate"]
    days = ctx["days"]
    ctx["edate"] = sdate + timedelta(days=days)
    today = date.today()
    if ctx["edate"] > today:
        ctx["edate"] = today
        ctx["days"] = (ctx["edate"] - sdate).days

    ctx["climo"] = {}
    if ctx["var"] == "tmpf":
        with get_sqlalchemy_conn("coop") as conn:
            res = conn.execute(
                sql_helper("""
    SELECT valid, high, low from ncei_climate91 where station = :station
                           """),
                {"station": ctx["_nt"].sts[ctx["station"]]["ncei91"]},
            )
            for row in res.mappings():
                ctx["climo"][row["valid"].strftime("%m%d")] = dict(
                    high=row["high"], low=row["low"]
                )
    col = "tmpf::int" if ctx["var"] == "tmpf" else ctx["var"]
    col = "dwpf::int" if ctx["var"] == "dwpf" else col
    with get_sqlalchemy_conn("asos") as conn:
        ctx["df"] = pd.read_sql(
            sql_helper(
                """
    SELECT valid at time zone 'UTC' as valid,
    extract(epoch from valid) * 1000 as ticks, {col} as datum
    from alldata WHERE station = :station and valid > :sts and valid < :ets
    and {varname} is not null and report_type != 1
    ORDER by valid ASC""",
                col=col,
                varname=ctx["var"],
            ),
            conn,
            params={
                "station": ctx["station"],
                "sts": sdate,
                "ets": sdate + timedelta(days=days),
            },
            index_col="valid",
        )
    if ctx["df"].empty:
        raise NoDataFound("No data found.")


def plotter(ctx: dict):
    """Go"""
    add_ctx(ctx)
    title = (
        f"{ctx['_sname']}\n"
        f"{MDICT[ctx['var']]} Timeseries {ctx['sdate']:%d %b %Y} - "
        f"{ctx['edate']:%d %b %Y}"
    )
    (fig, ax) = figure_axes(title=title, apctx=ctx)

    xticks = []
    xticklabels = []
    now = ctx["sdate"]
    cdates = []
    chighs = []
    clows = []
    oneday = timedelta(days=1)
    while ctx["climo"] and (now - oneday) <= ctx["edate"]:
        cdates.append(now)
        chighs.append(ctx["climo"][now.strftime("%m%d")]["high"])
        clows.append(ctx["climo"][now.strftime("%m%d")]["low"])
        if now.day == 1 or (now.day % 12 == 0 and ctx["days"] < 180):
            xticks.append(now)
            fmt = "%-d"
            if now.day == 1:
                fmt = "%-d\n%b"
            xticklabels.append(now.strftime(fmt))

        now += oneday
    while (now - oneday) <= ctx["edate"]:
        if now.day == 1 or (now.day % 12 == 0 and ctx["days"] < 180):
            xticks.append(now)
            fmt = "%-d"
            if now.day == 1:
                fmt = "%-d\n%b"
            xticklabels.append(now.strftime(fmt))
        now += oneday

    if chighs:
        chighs = np.array(chighs)
        clows = np.array(clows)
        ax.bar(
            cdates,
            chighs - clows,
            bottom=clows,
            width=1,
            align="edge",
            fc="lightblue",
            ec="lightblue",
            label="Daily Climatology",
        )
    # Construct a local timezone x axis
    x = (
        ctx["df"]
        .index.tz_localize(ZoneInfo("UTC"))
        .tz_convert(ctx["_nt"].sts[ctx["station"]]["tzname"])
        .tz_localize(None)
    )
    ax.plot(x.values, ctx["df"]["datum"], color="r", label="Hourly Obs")
    ax.set_ylabel("%s %s" % (MDICT[ctx["var"]], UNITS[ctx["var"]]))
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)
    ax.set_xlim(ctx["sdate"], ctx["edate"] + oneday)
    ax.set_ylim(top=ctx["df"].datum.max() + 15.0)
    ax.legend(loc=2, ncol=2)
    ax.axhline(32, linestyle="-.")
    ax.grid(True)
    return fig, ctx["df"]
