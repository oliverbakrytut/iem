<?php
require "../../include/forms.php";
require_once "../../include/memcache.php";
// Generate Cheezy PIL image
$pil = isset($_REQUEST["pil"]) ? substr(xssafe($_REQUEST["pil"]), 0, 6) : 'AFDDMX';

// Try to get it from memcached
$memcache = MemcacheSingleton::getInstance();
$val = $memcache->get("pil_{$pil}.png");
if ($val) {
    header("Content-type: image/png");
    die($val);
}
// Need to buffer the output so that we can save it to memcached later
ob_start();

$img = imagecreate(80, 80);
$white = imagecolorallocate($img, 255, 255, 255);
$black = imagecolorallocate($img, 0, 0, 0);
$ee = imagecolorallocate($img, 150, 150, 150);
imagefilledrectangle($img, 0, 0, 85, 85, $white);
imagettftext(
    $img,
    32,
    0,
    1,
    35,
    $black,
    "/usr/share/fonts/liberation-mono/LiberationMono-Bold.ttf",
    substr($pil, 0, 3)
);
imagettftext(
    $img,
    12,
    0,
    31,
    54,
    $ee,
    "/usr/share/fonts/liberation-mono/LiberationMono-Bold.ttf",
    "by"
);
imagettftext(
    $img,
    14,
    0,
    1,
    74,
    $black,
    "/usr/share/fonts/liberation-mono/LiberationMono-Bold.ttf",
    sprintf("NWS %s", substr($pil, 3, 3))
);

header("content-type: image/png");
imagepng($img);
imagedestroy($img);

$memcache->set("pil_{$pil}.png", ob_get_contents(), 0);
ob_end_flush();
