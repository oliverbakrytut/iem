"""
This plot generates a comparison between two hourly ASOS
observation values. The interactive chart version and raw data download
also presents the most recent UTC timestamp for that given combination.
Apps like these are very good at quickly seeing bad-data outliers :(
Please review any results you find here to see if the values match
what the reality may have been.  Additionally, for the case of mean
values, the presented timestamp is not of much use.
"""

from datetime import date, datetime

import pandas as pd
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import NoDataFound
from pyiem.plot import figure_axes

from iemweb.util import month2months

VDICT = {
    "dwpf": "Air Dew Point Temp [F]",
    "tmpf": "Air Temperature [F]",
    "feel": "Feels Like Temp [F]",
    "p01i": "Hourly Precipitation [inch]",
    "alti": "Pressure Altimeter [in Hg]",
    "mslp": "Pressure Mean Sea Level [mb]",
    "relh": "Relative Humidity [%]",
    "vsby": "Visibility [mile]",
    "gust": "Wind Gust [kts]",
    "sknt": "Wind Speed [kts]",
}
ADICT = {"min": "Minimum", "avg": "Average", "max": "Maximum"}
MDICT = {
    "all": "Entire Year",
    "spring": "Spring (MAM)",
    "summer": "Summer (JJA)",
    "fall": "Fall (SON)",
    "winter": "Winter (DJF)",
    "jan": "January",
    "feb": "February",
    "mar": "March",
    "apr": "April",
    "may": "May",
    "jun": "June",
    "jul": "July",
    "aug": "August",
    "sep": "September",
    "oct": "October",
    "nov": "November",
    "dec": "December",
}


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {"description": __doc__, "data": True, "cache": 86400}
    desc["highcharts"] = True
    desc["arguments"] = [
        dict(
            type="zstation",
            name="zstation",
            default="DSM",
            label="Select Station:",
            network="IA_ASOS",
        ),
        dict(
            type="select",
            name="month",
            default="all",
            label="Month Limiter",
            options=MDICT,
        ),
        dict(
            type="select",
            name="x",
            default="tmpf",
            label="X-Axis Categorical Variable",
            options=VDICT,
        ),
        dict(
            type="select",
            name="y",
            default="p01i",
            label="Y-Axis Variable to Summarize",
            options=VDICT,
        ),
        dict(
            type="select",
            name="agg",
            default="max",
            label="How to Summarize Y-axis Variable",
            options=ADICT,
        ),
        dict(
            type="year",
            name="syear",
            default=1920,
            minval=1920,
            label="Limit to Potential Start Year for the plot:",
        ),
    ]
    return desc


def get_highcharts(ctx: dict) -> str:
    """Fancy plot."""
    add_data(ctx)
    df = ctx["df"]
    ISO = "%Y-%m-%d %H:%M Z"
    containername = ctx["_e"]
    return (
        """
var x = """
        + str(df["x"].values.tolist())
        + """;
var dates = """
        + str(df["utc_valid"].dt.strftime(ISO).tolist())
        + """;
Highcharts.chart('"""
        + containername
        + """', {
    title: {text: '"""
        + ctx["title"]
        + """'},
    subtitle: {text: '"""
        + ctx["subtitle"]
        + """'},
    chart: {zoomType: 'x'},
    tooltip: {
        formatter: function() {
            var idx = x.indexOf(this.x);
            return "X: " + this.x + " Y: " + this.y + " @ " + dates[idx];
        }
    },
    xAxis: {
        categories: """
        + str(df["x"].values.tolist())
        + """,
        title: {text: '"""
        + ctx["xlabel"]
        + """'}},
    yAxis: {title: {text: '"""
        + ctx["ylabel"]
        + """'}},
    series: [{
        type: 'column',
        width: 0.8,
        tooltip: {
            valueDecimals: 2
        },
        data: """
        + str(df["y"].values.tolist())
        + """
    }]
});
    """
    )


def add_data(ctx):
    """Build out the context."""
    station = ctx["zstation"]
    month = ctx["month"]
    agg = ctx["agg"]
    x = ctx["x"]
    y = ctx["y"]
    # belt and suspenders
    assert x in VDICT
    assert y in VDICT
    assert agg in ADICT
    months = month2months(month)

    cast = "int" if x in ["tmpf", "dwpf", "feel"] else "real"
    basets = date(ctx["syear"], 1, 1)
    direction = "DESC" if agg == "max" else "ASC"
    with get_sqlalchemy_conn("asos") as conn:
        ctx["df"] = pd.read_sql(
            sql_helper(
                """
            WITH data as (
                SELECT {x}::{cast} as x, ({y}) as yv,
                first_value(valid at time zone 'UTC') OVER (
                    PARTITION by {x}::{cast}
                    ORDER by {y} {direction}, valid DESC) as timestamp
                from alldata where station = :station
                and extract(month from valid) = ANY(:months)
                and report_type = 3 and valid >= :basets
                and {x} is not null and {y} is not null
                ORDER by x ASC)
            SELECT x, {agg}(yv) as y, max(timestamp) as utc_valid from data
            GROUP by x ORDER by x ASC
        """,
                x=x,
                cast=cast,
                y=y,
                agg=agg,
                direction=direction,
            ),
            conn,
            params={
                "station": station,
                "months": months,
                "basets": basets,
            },
            index_col=None,
        )
    if ctx["df"].empty:
        raise NoDataFound("No Data Found.")
    ab = ctx["_nt"].sts[station]["archive_begin"]
    if ab is None:
        raise NoDataFound("Unknown station metadata.")
    minyear = ctx["df"]["utc_valid"].dt.year.min()
    ctx["xlabel"] = VDICT[ctx["x"]]
    ctx["ylabel"] = ADICT[ctx["agg"]] + " " + VDICT[ctx["y"]]
    ctx["title"] = ctx["_sname"]
    ctx["subtitle"] = ("%s %s by %s (month=%s) (%s-%s)") % (
        ADICT[agg],
        VDICT[y],
        VDICT[x],
        month.upper(),
        minyear,
        datetime.now().year,
    )


def plotter(ctx: dict):
    """Go"""
    add_data(ctx)
    df = ctx["df"]
    (fig, ax) = figure_axes(apctx=ctx)
    ax.bar(df["x"].values, df["y"].values, color="blue")
    ax.grid(True)
    ax.set_title(ctx["title"] + "\n" + ctx["subtitle"])
    ax.set_xlabel(ctx["xlabel"])
    ax.set_ylabel(ctx["ylabel"])
    df = df.rename({"x": VDICT[ctx["x"]], "y": VDICT[ctx["y"]]}, axis=1)
    return fig, df
