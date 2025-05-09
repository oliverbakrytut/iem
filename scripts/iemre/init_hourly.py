"""Generate the IEMRE hourly analysis file for a year"""

import os
from datetime import datetime

import click
import numpy as np
from pyiem.grid.nav import get_nav
from pyiem.iemre import DOMAINS, get_hourly_ncname
from pyiem.util import logger, ncopen, utc

LOG = logger()


def init_year(ts: datetime, domain: str, ci: bool) -> None:
    """
    Create a new NetCDF file for a year of our specification!
    """
    gridnav = get_nav("iemre", domain)
    fn = get_hourly_ncname(ts.year, domain)
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    if os.path.isfile(fn):
        LOG.info("Cowardly refusing to overwrite: %s", fn)
        return
    nc = ncopen(fn, "w")
    nc.title = f"IEM Hourly Reanalysis {ts.year} for domain: {domain}"
    nc.platform = "Grided Observations"
    nc.description = "IEM hourly analysis on a 0.125 degree grid"
    nc.institution = "Iowa State University, Ames, IA, USA"
    nc.source = "Iowa Environmental Mesonet"
    nc.project_id = "IEM"
    nc.realization = 1
    nc.Conventions = "CF-1.0"
    nc.contact = "Daryl Herzmann, akrherz@iastate.edu, 515-294-5978"
    nc.history = f"{utc():%d %B %Y} Generated"
    nc.comment = "No Comment at this time"

    # Setup Dimensions
    nc.createDimension("lat", gridnav.ny)
    nc.createDimension("lon", gridnav.nx)
    nc.createDimension("nv", 2)
    ts2 = datetime(ts.year + 1, 1, 1)
    days = 1 if ci else (ts2 - ts).days
    LOG.info("Year %s has %s days", ts.year, days)
    nc.createDimension("time", int(days) * 24)

    # Setup Coordinate Variables
    lat = nc.createVariable("lat", float, ("lat",))
    lat.units = "degrees_north"
    lat.long_name = "Latitude"
    lat.standard_name = "latitude"
    lat.axis = "Y"
    lat.bounds = "lat_bnds"
    # These are the grid centers
    lat[:] = gridnav.y_points

    lat_bnds = nc.createVariable("lat_bnds", float, ("lat", "nv"))
    lat_bnds[:, 0] = gridnav.y_edges[:-1]
    lat_bnds[:, 1] = gridnav.y_edges[1:]

    lon = nc.createVariable("lon", float, ("lon",))
    lon.units = "degrees_east"
    lon.long_name = "Longitude"
    lon.standard_name = "longitude"
    lon.axis = "X"
    lon.bounds = "lon_bnds"
    # These are the grid centers
    lon[:] = gridnav.x_points

    lon_bnds = nc.createVariable("lon_bnds", float, ("lon", "nv"))
    lon_bnds[:, 0] = gridnav.x_edges[:-1]
    lon_bnds[:, 1] = gridnav.x_edges[1:]

    tm = nc.createVariable("time", float, ("time",))
    tm.units = f"Hours since {ts.year}-01-01 00:00:0.0"
    tm.long_name = "Time"
    tm.standard_name = "time"
    tm.axis = "T"
    tm.calendar = "gregorian"
    tm[:] = np.arange(0, int(days) * 24)

    # Tracked variables
    hasdata = nc.createVariable("hasdata", np.int8, ("lat", "lon"))
    hasdata.units = "1"
    hasdata.long_name = "Analysis Available for Grid Cell"
    hasdata.coordinates = "lon lat"
    hasdata[:] = 0 if domain == "" else 1

    # can storage -128->127 actual values are 0 to 100
    skyc = nc.createVariable(
        "skyc", np.int8, ("time", "lat", "lon"), fill_value=-128
    )
    skyc.long_name = "ASOS Sky Coverage"
    skyc.stanard_name = "ASOS Sky Coverage"
    skyc.units = "%"
    skyc.valid_range = [0, 100]
    skyc.coordinates = "lon lat"

    # 0->65535
    tmpk = nc.createVariable(
        "tmpk", np.uint16, ("time", "lat", "lon"), fill_value=65535
    )
    tmpk.units = "K"
    tmpk.scale_factor = 0.01
    tmpk.long_name = "2m Air Temperature"
    tmpk.standard_name = "2m Air Temperature"
    tmpk.coordinates = "lon lat"

    # 0->65535  0 to 655.35
    dwpk = nc.createVariable(
        "dwpk", np.uint16, ("time", "lat", "lon"), fill_value=65335
    )
    dwpk.units = "K"
    dwpk.scale_factor = 0.01
    dwpk.long_name = "2m Air Dew Point Temperature"
    dwpk.standard_name = "2m Air Dew Point Temperature"
    dwpk.coordinates = "lon lat"

    # NOTE: we need to store negative numbers here, gasp
    # -32768 to 32767 so -65.5 to 65.5 mps
    uwnd = nc.createVariable(
        "uwnd", np.int16, ("time", "lat", "lon"), fill_value=32767
    )
    uwnd.scale_factor = 0.002
    uwnd.units = "meters per second"
    uwnd.long_name = "U component of the wind"
    uwnd.standard_name = "U component of the wind"
    uwnd.coordinates = "lon lat"

    # NOTE: we need to store negative numbers here, gasp
    # -32768 to 32767 so -65.5 to 65.5 mps
    vwnd = nc.createVariable(
        "vwnd", np.int16, ("time", "lat", "lon"), fill_value=32767
    )
    vwnd.scale_factor = 0.002
    vwnd.units = "meters per second"
    vwnd.long_name = "V component of the wind"
    vwnd.standard_name = "V component of the wind"
    vwnd.coordinates = "lon lat"

    # 0->65535  0 to 655.35
    p01m = nc.createVariable(
        "p01m", np.uint16, ("time", "lat", "lon"), fill_value=65535
    )
    p01m.units = "mm"
    p01m.scale_factor = 0.01
    p01m.long_name = "Precipitation"
    p01m.standard_name = "Precipitation"
    p01m.coordinates = "lon lat"
    p01m.description = "Precipitation accumulation for the hour valid time"

    v1 = nc.createVariable(
        "soil4t", np.uint16, ("time", "lat", "lon"), fill_value=65535
    )
    v1.units = "K"
    v1.scale_factor = 0.01
    v1.long_name = "4inch Soil Temperature"
    v1.standard_name = "4inch Soil Temperature"
    v1.coordinates = "lon lat"

    # Instantaneous solar radiation, so 0 to 1966 W/m^2
    rsds = nc.createVariable(
        "rsds", np.uint16, ("time", "lat", "lon"), fill_value=65535
    )
    rsds.units = "W m-2"
    rsds.scale_factor = 0.03
    rsds.long_name = "Downward Solar Radiation Flux"
    rsds.standard_name = "Downward Solar Radiation Flux at Surface"
    rsds.coordinates = "lon lat"

    nc.close()


@click.command()
@click.option("--year", type=int, required=True, help="Year to initialize")
@click.option("--ci", is_flag=True, help="Run in CI mode")
def main(year: int, ci: bool) -> None:
    """Go Main Go"""
    for domain in DOMAINS:
        init_year(datetime(year, 1, 1), domain, ci)
        if ci:
            with ncopen(get_hourly_ncname(year, domain), "a") as nc:
                nc.variables["rsds"][0] = 400


if __name__ == "__main__":
    main()
