"""text report of number of days with precip above threshold"""

from datetime import date

import numpy as np
import pandas as pd
from pyiem.database import get_sqlalchemy_conn
from pyiem.exceptions import NoDataFound

from iemweb.autoplot import ARG_STATION

CATS = np.array([0.01, 0.5, 1.0, 2.0, 3.0, 4.0])


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {
        "description": __doc__,
        "data": True,
        "report": True,
        "nopng": True,
    }
    desc["arguments"] = [
        ARG_STATION,
    ]
    return desc


def plotter(ctx: dict):
    """Go"""
    station = ctx["station"]

    bs = ctx["_nt"].sts[station]["archive_begin"]
    if bs is None:
        raise NoDataFound("No metadata found.")
    startyear = bs.year
    # 0.01, 0.5, 1, 2, 3, 4
    with get_sqlalchemy_conn("coop") as conn:
        df = pd.read_sql(
            """
            SELECT year, month,
            sum(case when precip >= %s then 1 else 0 end) as cat1,
            sum(case when precip >= %s then 1 else 0 end) as cat2,
            sum(case when precip >= %s then 1 else 0 end) as cat3,
            sum(case when precip >= %s then 1 else 0 end) as cat4,
            sum(case when precip >= %s then 1 else 0 end) as cat5,
            sum(case when precip >= %s then 1 else 0 end) as cat6
            from alldata WHERE station = %s GROUP by year, month
            ORDER by year, month
        """,
            conn,
            params=(
                CATS[0],
                CATS[1],
                CATS[2],
                CATS[3],
                CATS[4],
                CATS[5],
                station,
            ),
            index_col=["year", "month"],
        )

    res = (
        "# IEM Climodat https://mesonet.agron.iastate.edu/climodat/\n"
        f"# Report Generated: {date.today():%d %b %Y}\n"
        f"# Climate Record: {bs} -> {date.today()}\n"
        f"# Site Information: {ctx['_sname']}\n"
        "# Contact Information: Daryl Herzmann akrherz@iastate.edu "
        "515.294.5978\n"
        "# Number of days per year with precipitation at or "
        "above threshold [inch]\n"
        "# Partitioned by month of the year, 'ANN' represents "
        "the entire year\n"
    )

    for i, cat in enumerate(CATS):
        col = f"cat{i + 1}"
        res += (
            "YEAR %4.2f JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC ANN\n"
        ) % (cat,)
        for yr in range(startyear, date.today().year + 1):
            res += "%s %4.2f " % (yr, cat)
            for mo in range(1, 13):
                if (yr, mo) in df.index:
                    res += "%3.0f " % (df.at[(yr, mo), col],)
                else:
                    res += "  M "
            try:
                res += "%3.0f\n" % (df.loc[(yr, slice(1, 12)), col].sum(),)
            except KeyError:
                res += "   M\n"

    return None, df, res
