"""
This report displays the number of cycles between
two temperature thresholds of your choice.  A cycle representing one
round trip from below some threshold to above the second threshold.
"""

from datetime import date

import pandas as pd
from pyiem.database import get_dbconn
from pyiem.exceptions import NoDataFound

from iemweb.autoplot import ARG_STATION


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
        dict(
            type="text",
            name="thres1",
            default="26-38",
            label="Threshold 1 (lower-upper) (F)",
        ),
        dict(
            type="text",
            name="thres2",
            default="24-40",
            label="Threshold 2 (lower-upper) (F)",
        ),
        dict(
            type="text",
            name="thres3",
            default="20-44",
            label="Threshold 3 (lower-upper) (F)",
        ),
        dict(
            type="text",
            name="thres4",
            default="14-50",
            label="Threshold 4 (lower-upper) (F)",
        ),
    ]
    return desc


def make(val):
    """Convert into thresholds"""
    return [int(a) for a in val.split("-")]


def plotter(ctx: dict):
    """Go"""
    pgconn = get_dbconn("coop")
    cursor = pgconn.cursor()
    station = ctx["station"]
    thres1 = ctx["thres1"]
    thres2 = ctx["thres2"]
    thres3 = ctx["thres3"]
    thres4 = ctx["thres4"]
    thres = [thres1, thres2, thres3, thres4]

    prs = [make(thres1), make(thres2), make(thres3), make(thres4)]

    s = ctx["_nt"].sts[station]["archive_begin"]
    e = date.today()

    if s is None:
        raise NoDataFound("Unknown metadata.")
    res = """\
# IEM Climodat https://mesonet.agron.iastate.edu/climodat/
# Report Generated: %s
# Climate Record: %s -> %s
# Site Information: [%s] %s
# Contact Information: Daryl Herzmann akrherz@iastate.edu 515.294.5978
# seasonal temperature cycles per year, spring is Jan-Jun, fall is Jul-Dec
# 1 CYCLE IS A TEMPERATURE VARIATION FROM A VALUE BELOW A THRESHOLD
# TO A VALUE EXCEEDING A THRESHOLD.  THINK OF IT AS FREEZE/THAW CYCLES
# FIRST DATA COLUMN WOULD BE FOR CYCLES EXCEEDING 26 AND 38 DEGREES F
THRES  %2.0f-%2.0f   %2.0f-%2.0f   %2.0f-%2.0f   %2.0f-%2.0f   \
%2.0f-%2.0f   %2.0f-%2.0f   %2.0f-%2.0f   %2.0f-%2.0f
YEAR   SPRING  FALL    SPRING  FALL    SPRING  FALL    SPRING  FALL
""" % (
        e.strftime("%d %b %Y"),
        s,
        e,
        station,
        ctx["_nt"].sts[station]["name"],
        prs[0][0],
        prs[0][1],
        prs[0][0],
        prs[0][1],
        prs[1][0],
        prs[1][1],
        prs[1][0],
        prs[1][1],
        prs[2][0],
        prs[2][1],
        prs[2][0],
        prs[2][1],
        prs[3][0],
        prs[3][1],
        prs[3][0],
        prs[3][1],
    )

    df = pd.DataFrame(
        {
            thres1 + "s": 0.0,
            thres1 + "f": 0.0,
            thres2 + "s": 0.0,
            thres2 + "f": 0.0,
            thres3 + "s": 0.0,
            thres3 + "f": 0.0,
            thres4 + "s": 0.0,
            thres4 + "f": 0.0,
        },
        index=pd.Series(range(s.year, e.year + 1), name="year"),
    )

    cycle_pos = [-1, -1, -1, -1]

    cursor.execute(
        "SELECT day, high, low from alldata WHERE station = %s and "
        "high is not null and low is not null ORDER by day ASC",
        (station,),
    )
    for row in cursor:
        ts = row[0]
        high = row[1]
        low = row[2]

        for i, (lower, upper) in enumerate(prs):
            ckey = thres[i] + ("s" if ts.month < 7 else "f")

            # cycles lower
            if cycle_pos[i] == 1 and low < lower:
                cycle_pos[i] = -1
                df.loc[ts.year, ckey] += 0.5

            # cycled higher
            if cycle_pos[i] == -1 and high > upper:
                cycle_pos[i] = 1
                df.loc[ts.year, ckey] += 0.5
    cursor.close()
    pgconn.close()
    for yr, row in df.iterrows():
        res += ("%s   %-8i%-8i%-8i%-8i%-8i%-8i%-8i%-8i\n") % (
            yr,
            row[f"{thres1}s"],
            row[f"{thres1}f"],
            row[f"{thres2}s"],
            row[f"{thres2}f"],
            row[f"{thres3}s"],
            row[f"{thres3}f"],
            row[f"{thres4}s"],
            row[f"{thres4}f"],
        )

    res += ("AVG    %-8.1f%-8.1f%-8.1f%-8.1f%-8.1f%-8.1f%-8.1f%-8.1f\n") % (
        df[thres1 + "s"].mean(),
        df[thres1 + "f"].mean(),
        df[thres2 + "s"].mean(),
        df[thres2 + "f"].mean(),
        df[thres3 + "s"].mean(),
        df[thres3 + "f"].mean(),
        df[thres4 + "s"].mean(),
        df[thres4 + "f"].mean(),
    )

    return None, df, res
