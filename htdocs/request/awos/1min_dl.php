<?php
require_once "../../../config/settings.inc.php";
require_once "../../../include/database.inc.php";
require_once "../../../include/network.php";
require_once "../../../include/forms.php";
$nt = new NetworkTable("IA_ASOS");

$skycover = array(
    0 => "NOREPORT",
    1 => "SCATTERED",
    2 => "BROKEN",
    4 => "OVERCAST",
    8 => "OBSCURATION",
    16 => "UNKNOWN",
    17 => "OBSCURATION",
    18 => "OBSCURATION",
    20 => "OBSCURATION",
    32 => "INDEFINITE",
    64 => "CLEAR",
    128 => "FEW",
    255 => "MISSING"
);

$gis = isset($_GET["gis"]) ? xssafe($_GET["gis"]) : 'no';
$delim = isset($_GET["delim"]) ? xssafe($_GET["delim"]) : ",";
$sample = isset($_GET["sample"]) ? xssafe($_GET["sample"]) : "1min";
$what = isset($_GET["what"]) ? xssafe($_GET["what"]) : 'dl';
$tz = isset($_GET["tz"]) ? xssafe($_GET["tz"]) : 'UTC';

$day1 = isset($_GET["day1"]) ? xssafe($_GET["day1"]) : die("No day1 specified");
$day2 = isset($_GET["day2"]) ? xssafe($_GET["day2"]) : die("No day2 specified");
$month1 = isset($_GET["month1"]) ? xssafe($_GET["month1"]) : die("No month1 specified");
$month2 = isset($_GET["month2"]) ? xssafe($_GET["month2"]) : die("No month2 specified");
$year1 = isset($_GET["year1"]) ? xssafe($_GET["year1"]) : die("No year1 specified");
$year2 = isset($_GET["year2"]) ? xssafe($_GET["year2"]) : die("No year2 specified");
$hour1 = isset($_GET["hour1"]) ? xssafe($_GET["hour1"]) : die("No hour1 specified");
$hour2 = isset($_GET["hour2"]) ? xssafe($_GET["hour2"]) : die("No hour2 specified");
$minute1 = isset($_GET["minute1"]) ? xssafe($_GET["minute1"]) : die("No minute1 specified");
$minute2 = isset($_GET["minute2"]) ? xssafe($_GET["minute2"]) : die("No minute2 specified");
$vars = isset($_GET["vars"]) ? $_GET["vars"] : die("No vars specified");

$stations = $_GET["station"];
$selectAll = false;
foreach ($stations as $key => $value) {
    if ($value === "_ALL") {
        $selectAll = true;
        continue;
    }
    if (strlen($value) > 4 && !array_key_exists($value, $nt->table)) {
        xssafe("<tag>");
    }
}
if ($selectAll) {
    $stations = array_keys($nt->table);
}

if (isset($_GET["day"]))
    die("Incorrect CGI param, use day1, day2");

$ts1 = mktime($hour1, $minute1, 0, $month1, $day1, $year1) or
    die("Invalid Date Format");
$ts2 = mktime($hour2, $minute2, 0, $month2, $day2, $year2) or
    die("Invalid Date Format");

if ($selectAll && $day1 != $day2)
    $ts2 = $ts1 + 86400;

$num_vars = count($vars);
if ($num_vars == 0)  die("You did not specify data");

$sqlStr = "SELECT station, ";
for ($i = 0; $i < $num_vars; $i++) {
    $sqlStr .= xssafe($vars[$i]) . " as var{$i}, ";
}

$sqlTS1 = date("Y-m-d H:i", $ts1);
$sqlTS2 = date("Y-m-d H:i", $ts2);
$nicedate = date("Y-m-d", $ts1);

$sampleStr = array(
    "1min" => "1",
    "5min" => "5",
    "10min" => "10",
    "20min" => "20",
    "1hour" => "60"
);

$d = array("space" => " ", "comma" => ",", "tab" => "\t");

$sqlStr .= "to_char(valid, 'YYYY-MM-DD HH24:MI') as dvalid from alldata ";
$sqlStr .= " WHERE valid >= '" . $sqlTS1 . "' and valid <= '" . $sqlTS2 . "' ";
$sqlStr .= " and extract(minute from valid)::int % " . $sampleStr[$sample] . " = 0 ";
$sqlStr .= " and station = ANY($1) ORDER by valid ASC";

if ($what == "download") {
    header("Content-type: application/octet-stream");
    header("Content-Disposition: attachment; filename=changeme.txt");
} else {
    header("Content-type: text/plain");
}

$conn = iemdb("awos");

$tzn = "local";
if ($tz == "UTC") {
    $tzn = "UTC";
    $result = pg_exec($conn, "SET TIME ZONE 'UTC'");
}

$stname = iem_pg_prepare($conn, $sqlStr);
$rs = pg_execute($conn, $stname, Array("{ " . implode(",", $stations) . " }"));

if ($gis == "yes") {
    echo "station,station_name,lat,lon,valid($tzn),";
} else {
    echo "station,station_name,valid($tzn),";
}
for ($j = 0; $j < $num_vars; $j++) {
    echo $vars[$j] . $d[$delim];
    if ($vars[$j] == "ca1") echo "ca1code" . $d[$delim];
    if ($vars[$j] == "ca2") echo "ca2code" . $d[$delim];
    if ($vars[$j] == "ca3") echo "ca3code" . $d[$delim];
}
echo "\n";

for ($i = 0; $row = pg_fetch_assoc($rs); $i++) {
    $sid = $row["station"];
    echo $sid . $d[$delim] . $nt->table[$sid]["name"];
    if ($gis == "yes") {
        echo  $d[$delim] . $nt->table[$sid]["lat"] . $d[$delim] .  $nt->table[$sid]["lon"];
    }
    echo $d[$delim] . $row["dvalid"] . $d[$delim];
    for ($j = 0; $j < $num_vars; $j++) {
        echo $row["var" . $j] . $d[$delim];
        if ($vars[$j] == "ca1") echo $skycover[$row["var" . $j]] . $d[$delim];
        if ($vars[$j] == "ca2") echo $skycover[$row["var" . $j]] . $d[$delim];
        if ($vars[$j] == "ca3") echo $skycover[$row["var" . $j]] . $d[$delim];
    }
    echo "\n";
}
