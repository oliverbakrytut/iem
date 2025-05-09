"""
This plot presents the range between the min
and maximum observation of your choice for a given station and a given
year.  Some of these values are only computed based on hourly reports,
so they would be represent a true min and max of a continuously observed
variable.
"""

from datetime import datetime, timedelta

import matplotlib.dates as mdates
import pandas as pd
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import NoDataFound
from pyiem.plot import figure

PDICT = {
    "below": "Daily Range Below Emphasis",
    "atbelow": "Daily Range At or Below Emphasis",
    "touches": "Daily Range Touches Emphasis",
    "above": "Daily Range At or Above Emphasis",
}

PDICT2 = {
    "tmpf": "Air Temperature",
    "dwpf": "Dew Point Temperature",
    "feel": "Feels Like Temperature",
    "rh": "Relative Humidity",
}


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {"description": __doc__, "data": True}
    today = datetime.now()
    desc["arguments"] = [
        dict(
            type="zstation",
            name="zstation",
            default="AMW",
            label="Select Station:",
            network="IA_ASOS",
        ),
        dict(
            type="year",
            min=1900,
            name="year",
            default=today.year,
            label="Select Year:",
        ),
        dict(
            type="int",
            name="emphasis",
            default="-99",
            label=(
                "Temperature(&deg;F) or RH(%) Line of Emphasis (-99 disables):"
            ),
        ),
        dict(
            type="select",
            name="var",
            label="Which variable to plot?",
            default="dwpf",
            options=PDICT2,
        ),
        dict(
            type="select",
            name="opt",
            label="Option for Highlighting",
            default="touches",
            options=PDICT,
        ),
    ]
    return desc


def plotter(ctx: dict):
    """Go"""
    station = ctx["zstation"]
    year = ctx["year"]
    emphasis = ctx["emphasis"]
    opt = ctx["opt"]
    varname = ctx["var"]
    with get_sqlalchemy_conn("iem") as conn:
        df = pd.read_sql(
            sql_helper(
                """
            select day, max_{varname}, min_{varname}
            from {table} s JOIN stations t on (s.iemid = t.iemid)
            where t.id = :station and t.network = :network and
            max_{varname} is not null and
            min_{varname} is not null
            ORDER by day ASC
        """,
                varname=varname,
                table=f"summary_{year}",
            ),
            conn,
            params={"station": station, "network": ctx["network"]},
            index_col="day",
        )
    if df.empty:
        raise NoDataFound("No Data Found!")
    df["range"] = df[f"max_{varname}"] - df[f"min_{varname}"]

    minval = df[f"min_{varname}"].min()
    maxval = df[f"max_{varname}"].max()
    title = (
        f"{ctx['_sname']}:: {year} "
        f"Daily Min/Max {PDICT2[varname]}\n"
        f"Period: {df.index.values[0]:%-d %B} to {df.index.values[-1]:%-d %B}"
        f" , Min: {minval:.0f} Max: {maxval:.0f}"
    )
    fig = figure(title=title, apctx=ctx)
    ax = fig.add_axes((0.1, 0.15, 0.8, 0.75))
    bars = ax.bar(
        df.index.values,
        df["range"].values,
        ec="g",
        fc="g",
        bottom=df[f"min_{varname}"].values,
        zorder=1,
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d\n%b"))
    hits = []
    if emphasis > -99:
        for i, mybar in enumerate(bars):
            minval = mybar.get_y()
            maxval = mybar.get_y() + mybar.get_height()
            if (
                (maxval >= emphasis >= minval and opt == "touches")
                or (minval >= emphasis and opt == "above")
                or (maxval < emphasis and opt == "below")
                or (minval <= emphasis and opt == "atbelow")
            ):
                mybar.set_facecolor("r")
                mybar.set_edgecolor("r")
                hits.append(df.index.values[i])
        ax.axhline(emphasis, lw=2, color="k")
        ax.text(
            df.index.values[-1] + timedelta(days=2),
            emphasis,
            f"{emphasis}",
            ha="left",
            va="center",
        )
    ax.grid(True)
    ll = r"$^\circ$F" if varname != "rh" else "%"
    ax.set_ylabel(f"{PDICT2[varname]} {ll}")
    ax.set_xlabel(
        f"Days meeting emphasis: {len(hits)}, "
        f"first: {hits[0].strftime('%B %d') if hits else 'None'} "
        f"last: {hits[-1].strftime('%B %d') if hits else 'None'}"
    )
    delta = timedelta(days=1)
    ax.set_xlim(df.index.values[0] - delta, df.index.values[-1] + delta)
    return fig, df
