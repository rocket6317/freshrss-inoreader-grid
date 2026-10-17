<?php
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
	http_response_code(404);
	exit;
}

$freshRoot = getenv('FRESHRSS_ROOT') ?: dirname(__DIR__, 3);
require $freshRoot . '/constants.php';
require LIB_PATH . '/lib_rss.php';
require dirname(__DIR__) . '/extension.php';

function check(bool $ok, string $label): void {
	if (!$ok) {
		throw new RuntimeException($label);
	}
	echo 'PASS ', $label, PHP_EOL;
}

Minz_Translate::init('en');
FreshRSS_Context::setUserConf(FreshRSS_UserConfiguration::init(FRESHRSS_PATH . '/config-user.default.php'));
$metadata = json_decode(file_get_contents(dirname(__DIR__) . '/metadata.json'), true, flags: JSON_THROW_ON_ERROR);
$metadata['path'] = dirname(__DIR__);
$extension = new InoreaderGridExtension($metadata);
$extension->init();
check($extension->getType() === 'user', 'native extension metadata and asset registration');

Minz_Request::_controllerName('index');
Minz_Request::_actionName('normal');
$entry = new FreshRSS_Entry(0, 'synthetic', 'Synthetic &amp; safe', '', '<p>Original readable content</p>',
	'https://example.invalid/test', 1792231200);
$entry->_id('123');
$entry->_attribute('thumbnail', ['url' => 'https://example.invalid/image?a=1&amp;b=&quot;test&quot;']);
$entry->_attribute('enclosures', [
	['url' => 'https://example.invalid/large?a=1&amp;b=&quot;test&quot;', 'type' => 'image/jpeg', 'width' => 1200, 'height' => 800],
	['url' => 'https://example.invalid/video.mp4', 'type' => 'video/mp4'],
]);
$result = $extension->entryBeforeDisplay($entry);
$dom = new DOMDocument();
$dom->loadHTML($result->content(false));
$span = $dom->getElementsByTagName('span')->item(0);
check($span instanceof DOMElement && $span->getAttribute('class') === 'ig-entry-meta', 'display metadata added to real FreshRSS entry');
check($span->getAttribute('data-image') === 'https://example.invalid/image?a=1&b="test"', 'metadata encoding preserves ampersands and quotes');
$images = json_decode($span->getAttribute('data-images'), true, flags: JSON_THROW_ON_ERROR);
check(count($images) === 1 && $images[0]['width'] === 1200 &&
	$images[0]['url'] === 'https://example.invalid/large?a=1&b="test"', 'higher-resolution enclosure metadata is escaped correctly and excludes video');
check(str_contains($result->content(false), '<p>Original readable content</p>'), 'original article content retained');
$anchor = $dom->getElementsByTagName('a')->item(0);
check($anchor instanceof DOMElement && str_contains($anchor->getAttribute('href'), 'a=bookmark') &&
	str_contains($anchor->getAttribute('href'), 'id=123'), 'native bookmark URL available when native toolbar is hidden');

foreach (['reader', 'rss', 'global'] as $action) {
	Minz_Request::_actionName($action);
	$other = new FreshRSS_Entry(0, 'synthetic', '', '', '<p>Unchanged</p>');
	check($extension->entryBeforeDisplay($other)->content(false) === '<p>Unchanged</p>', $action . ' view left untouched');
}
