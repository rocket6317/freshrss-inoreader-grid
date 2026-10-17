<?php
declare(strict_types=1);

final class InoreaderGridExtension extends Minz_Extension {
	public function init(): void {
		Minz_View::appendStyle($this->getFileUrl('grid.css'));
		Minz_View::appendScript($this->getFileUrl('grid.js'), false, true, false);
		$this->registerHook('entry_before_display', [$this, 'entryBeforeDisplay']);
	}

	/** Display-only metadata: never saved to the database or sent elsewhere. */
	public function entryBeforeDisplay(FreshRSS_Entry $entry): FreshRSS_Entry {
		if (Minz_Request::controllerName() !== 'index' || Minz_Request::actionName() !== 'normal') {
			return $entry;
		}
		$thumbnail = $entry->thumbnail();
		$values = [
			'date' => $entry->date(),
			'datetime' => $entry->machineReadableDate(),
			'image' => $thumbnail['url'] ?? '',
			'image-width' => $thumbnail['width'] ?? 0,
			'image-height' => $thumbnail['height'] ?? 0,
		];
		$metadata = '<span class="ig-entry-meta" hidden';
		foreach ($values as $key => $value) {
			// FreshRSS stores HTML-encoded strings; decode before attribute encoding.
			$value = html_entity_decode((string)$value, ENT_QUOTES | ENT_HTML5, 'UTF-8');
			$metadata .= ' data-' . $key . '="' . htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '"';
		}
		$images = [];
		foreach ($entry->enclosures() as $enclosure) {
			$url = html_entity_decode($enclosure['url'], ENT_QUOTES | ENT_HTML5, 'UTF-8');
			$type = strtolower($enclosure['type'] ?? '');
			if (!str_starts_with($type, 'image/') && ($enclosure['medium'] ?? '') !== 'image' &&
				!($type === '' && preg_match('/\.(?:jpe?g|png|webp|avif|gif)(?:[?#]|$)/i', $url))) {
				continue;
			}
			$images[] = ['url' => $url, 'width' => (int)($enclosure['width'] ?? 0), 'height' => (int)($enclosure['height'] ?? 0)];
		}
		$metadata .= ' data-images="' . htmlspecialchars(json_encode($images, JSON_INVALID_UTF8_SUBSTITUTE) ?: '[]',
			ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '"';
		$bookmarkUrl = Minz_Url::display([
			'c' => 'entry', 'a' => 'bookmark',
			'params' => ['id' => $entry->id(), 'is_favorite' => $entry->isFavorite() ? '0' : '1'],
		]);
		// Native mark_favorite() needs a bookmark URL even when both native bars hide it.
		$entry->_content($metadata . '><a class="bookmark" href="' . $bookmarkUrl . '"></a></span>' . $entry->content(false));
		return $entry;
	}
}
