<?php

$filename = $argv[1];

try {
	$compressedData = new PharData($filename);
	$compressedData->decompress();

	$fname = explode('.', $filename);
	$targetName = $fname[0].'.'.$fname[1];

	echo "[x] extracted from .gz to " . $targetName . "\n";

	$compressedData = new PharData($targetName);
	$compressedData->extractTo('.', null, TRUE);

	unlink($targetName);

	echo "[x] file " . $targetName . " removed\n";

    echo "[x] decompressed succesfully\n";
} catch (Exception $e) {
	echo $e->getMessage();
}

?>