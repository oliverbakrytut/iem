<?php
require_once "../../../../config/settings.inc.php";
require_once "../../../../include/database.inc.php";
require_once "../../../../include/forms.php";
require_once "../../../../include/network.php";
require_once "../../../../include/vendor/mapscript.php";

$coopdb = iemdb("coop");

$var = isset($_GET["var"]) ? xssafe($_GET["var"]) : "gdd50";
$year = get_int404("year", date("Y"));
$smonth = get_int404("smonth", 5);
$sday = get_int404("sday", 1);
$emonth = get_int404("emonth", date("m"));
$eday = get_int404("eday", date("d"));
$network = isset($_REQUEST["network"]) ? xssafe($_REQUEST["network"]) : "IACLIMATE";
if (strlen($network) > 9){
    xssafe("<tag>");
}

$nt = new NetworkTable($network);
$cities = $nt->table;

$sts = new DateTime("{$year}-{$smonth}-{$sday}");
$ets = new DateTime("{$year}-{$emonth}-{$eday}");


function mktitlelocal($map, $imgObj, $titlet)
{

    $layer = $map->getLayerByName("credits26915");

    // point feature with text for location
    $point = new pointobj();
    $point->setXY(0, 10);
    $point->draw($map, $layer, $imgObj, 0, $titlet);
}

function plotNoData($map, $img)
{
    $layer = $map->getLayerByName("credits");

    $point = new pointobj();
    $point->setXY(100, 200);
    $point->draw(
        $map,
        $layer,
        $img,
        1,
        "  No data found for this date! "
    );
}

$varDef = array(
    "gdd32" => "Growing Degree Days (base=32)",
    "gdd41" => "Growing Degree Days (base=41)",
    "gdd46" => "Growing Degree Days (base=46)",
    "gdd48" => "Growing Degree Days (base=48)",
    "gdd50" => "Growing Degree Days (base=50)",
    "gdd51" => "Growing Degree Days (base=51)",
    "gdd52" => "Growing Degree Days (base=52)",
    "cdd65" => "Cooling Degree Days (base=65)",
    "hdd65" => "Heating Degree Days (base=65)",
    "et" => "Potential Evapotranspiration",
    "prec" => "Precipitation",
    "sgdd50" => "Soil Growing Degree Days (base=50)",
    "sdd86" => "Stress Degree Days (base=86)",
    "mintemp" => "Minimum Temperature [F]",
    "maxtemp" => "Maximum Temperature [F]",
);

$rnd = array(
    "gdd32" => 0,
    "gdd41" => 0,
    "gdd46" => 0,
    "gdd48" => 0,
    "gdd50" => 0,
    "gdd51" => 0,
    "gdd52" => 0,
    "et" => 2,
    "prec" => 2,
    "sgdd50" => 0,
    "sdd86" => 0,
    "cdd65" => 0,
    "hdd65" => 0,
    "mintemp" => 0,
    "maxtemp" => 0
);
$myStations = $cities;
$height = 480;
$width = 640;

$map = new MapObj("../../../../data/gis/base4326.map");
$map->imagecolor->setRGB(255, 255, 255);
$map->setSize(1024, 768);

$state = substr($network, 0, 2);
$dbconn = iemdb("postgis");
$stname = iem_pg_prepare($dbconn,
    "SELECT ST_xmin(g), ST_xmax(g), ST_ymin(g), ST_ymax(g) from (
        select ST_Extent(the_geom) as g from states 
        where state_abbr = $1
        ) as foo");
$rs = pg_execute($dbconn, $stname, Array($state));
$row = pg_fetch_assoc($rs);
$buf = 0.2; // 35km
$xsz = $row["st_xmax"] - $row["st_xmin"];
$ysz = $row["st_ymax"] - $row["st_ymin"];
$minx = $row["st_xmin"] - $buf;
$maxx = $row["st_xmax"] + $buf;
$miny = $row["st_ymin"] - $buf;
$maxy = $row["st_ymax"] + $buf;
$map->setextent($minx, $miny, $maxx, $maxy);

$counties = $map->getLayerByName("counties");
$counties->__set("status", MS_ON);

$states = $map->getLayerByName("states");
$states->__set("status", MS_ON);

$bar640t = $map->getLayerByName("bar640t");
$bar640t->__set("status", MS_ON);

$snet = $map->getLayerByName("snet");
$snet->__set("status", MS_ON);

$ponly = $map->getLayerByName("pointonly");
$ponly->__set("status", MS_ON);

$img = $map->prepareImage();
$counties->draw($map, $img);
$states->draw($map, $img);
$bar640t->draw($map, $img);

// Allow 15 labels in each direction?
$dy = ($map->extent->maxy - $map->extent->miny) / 25;
$dx = ($map->extent->maxx - $map->extent->minx) / 25;

$stname = iem_pg_prepare($coopdb, <<<EOM
    SELECT station, 
    sum(precip) as s_prec,
    sum(gddxx(32, 86, high, low)) as s_gdd32,
    sum(gddxx(41, 86, high, low)) as s_gdd41,
    sum(gddxx(46, 86, high, low)) as s_gdd46,
    sum(gddxx(48, 86, high, low)) as s_gdd48,
    sum(gddxx(50, 86, high, low)) as s_gdd50,
    sum(gddxx(51, 86, high, low)) as s_gdd51,
    sum(gddxx(52, 86, high, low)) as s_gdd52,
    sum(cdd(high, low, 65)) as s_cdd65,
    sum(hdd(high, low, 65)) as s_hdd65,
    sum(sdd86(high,low)) as s_sdd86, min(low) as s_mintemp,
    max(high) as s_maxtemp from alldata_{$state}
    WHERE day >= $1 and day <= $2
    and substr(station, 3, 4) != '0000' and substr(station, 3, 1) != 'C'
    GROUP by station 
    ORDER by station ASC
EOM
);
$rs = pg_execute($coopdb, $stname, array(
    $sts->format("Y-m-d"),
    $ets->format("Y-m-d")
));

$used = Array();

for ($i = 0; $row = pg_fetch_assoc($rs); $i++) {

    $ukey = $row["station"];
    if (!isset($cities[$ukey])) continue;
    $key = sprintf(
        "%.0f_%.0f",
        ($cities[$ukey]["lon"] - $map->extent->minx) / $dx,
        ($cities[$ukey]["lat"] - $map->extent->miny) / $dy,
    );
    if (in_array($key, $used)) continue;
    $used[] = $key;
    // Red Dot...
    $pt = new PointObj();
    $pt->setXY($cities[$ukey]['lon'], $cities[$ukey]['lat'], 0);
    $pt->draw($map, $ponly, $img, 2, "");

    // City Name
    $pt = new PointObj();
    $pt->setXY($cities[$ukey]['lon'], $cities[$ukey]['lat'], 0);
    $pt->draw($map, $snet, $img, 3, substr($ukey, 2, 4));

    // Value UL
    $pt = new PointObj();
    $pt->setXY($cities[$ukey]['lon'], $cities[$ukey]['lat'], 0, "");
    $pt->draw(
        $map,
        $snet,
        $img,
        0,
        round($row["s_" . $var], $rnd[$var])
    );
}
if ($i == 0)
    plotNoData($map, $img);

$title = sprintf(
    "%s (%s through %s)",
    $varDef[$var],
    $sts->format("Y-m-d"),
    $ets->format("Y-m-d")
);

mktitlelocal($map, $img, $title);
$map->drawLabelCache($img);

header("Content-type: image/png");
echo $img->getBytes();
