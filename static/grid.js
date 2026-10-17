/* InoreaderGrid: progressive enhancement of FreshRSS 1.30.1 normal view. */
(() => {
	'use strict';
	function init() {
		const stream = document.querySelector('#stream.normal');
		if (!stream || typeof toggleContent !== 'function' || typeof context === 'undefined' ||
			!window.HTMLDialogElement || !HTMLDialogElement.prototype.showModal) return;
		const root = document.documentElement;
		if (root.classList.contains('ig-enabled')) return;
		root.classList.add('ig-enabled');
		// Grid scrolling must not mark unopened cards read or remove the return target.
		// These are page-local overrides; nothing is persisted to user configuration.
		context.auto_mark_scroll = false;
		context.auto_remove_article = false;
		const aside = document.querySelector('.aside.aside_feed');
		const asideButton = document.querySelector('#nav_menu_toggle_aside button');
		aside?.classList.remove('visible');
		aside?.classList.add('is-hidden');
		asideButton?.classList.remove('active');
		asideButton?.setAttribute('aria-expanded', 'false');
		function closeAside() {
			if (!aside?.classList.contains('visible')) return;
			asideButton?.click();
			asideButton?.focus({ preventScroll: true });
		}
		if (aside && asideButton) {
			const sidebarHeader = element('div', 'ig-sidebar-header');
			const sidebarClose = button('Close feed navigation', 'Close ×', event => {
				event.preventDefault();
				event.stopPropagation();
				closeAside();
			});
			sidebarClose.classList.add('ig-sidebar-close');
			sidebarHeader.append(element('span', 'ig-sidebar-label', 'Feeds'), sidebarClose);
			aside.prepend(sidebarHeader);
			new MutationObserver(() => asideButton.setAttribute('aria-expanded', String(aside.classList.contains('visible'))))
				.observe(aside, { attributes: true, attributeFilter: ['class'] });
		}

		function element(tag, cls, text) {
			const node = document.createElement(tag);
			if (cls) node.className = cls;
			if (text) node.textContent = text;
			return node;
		}
		function button(label, text, action) {
			const node = element('button', 'ig-control', text);
			node.type = 'button';
			node.title = label;
			node.setAttribute('aria-label', label);
			node.addEventListener('click', action);
			return node;
		}
		function imageURL(value) {
			if (!value) return '';
			try {
				const url = new URL(value, document.baseURI);
				return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
			} catch { return ''; }
		}
		function imageInfo(value) {
			const url = new URL(value);
			let match;
			// Compare publisher asset IDs, not crops or host aliases. Never rewrite URLs.
			if (/(^|\.)liverpoolecho\.co\.uk$/.test(url.hostname) &&
				(match = url.pathname.match(/\/article(\d+)\.ece\/ALTERNATES\/s(\d+)\w*\/(.+)$/i))) {
				return { key: `echo:${match[1]}:${match[3]}`, width: Number(match[2]) };
			}
			if (/(^|\.)wirralglobe\.co\.uk$/.test(url.hostname) &&
				(match = url.pathname.match(/^\/resources\/images\/(\d+)(?:\.[a-z]+)?\/?$/i))) {
				return { key: `globe:${match[1]}`, width: Number(url.searchParams.get('type')?.match(/mds-article-(\d+)/)?.[1]) || 0,
					original: !url.search };
			}
			if (url.hostname === 'ichef.bbci.co.uk' && (match = url.pathname.match(/^(\/ace\/standard\/)\d+(\/.*)$/))) {
				return { key: `bbc:${match[2]}`, width: Number(url.pathname.match(/\/standard\/(\d+)/)[1]) };
			}
			const width = Number(url.searchParams.get('width') || url.searchParams.get('w')) || 0;
			for (const key of ['w', 'width', 'h', 'height', 'dpr', 'q', 'quality', 'fit', 'format', 'auto']) url.searchParams.delete(key);
			url.searchParams.sort();
			url.hash = '';
			return { key: url.href, width };
		}
		function imageVariants(entry) {
			const meta = entry.querySelector('.ig-entry-meta');
			const all = new Map();
			const groups = new Map();
			const pixels = value => /^\d+(?:\.\d+)?(?:px)?$/.test(value || '') ? parseFloat(value) : 0;
			function add(value, width = 0, node = null) {
				const url = imageURL(value);
				if (!url) return null;
				const info = imageInfo(url);
				const record = { url, key: info.key, width: info.width || Number(width) || 0, original: Boolean(info.original), node };
				const previous = all.get(url);
				if (previous) {
					previous.width = Math.max(previous.width, record.width);
					previous.node ||= node;
					return previous;
				}
				all.set(url, record);
				return record;
			}
			let lead = add(meta?.dataset.image, meta?.dataset.imageWidth);
			try {
				const images = JSON.parse(meta?.dataset.images || '[]');
				if (Array.isArray(images)) images.forEach(image => { if (image && typeof image.url === 'string') add(image.url, image.width); });
			} catch { /* Older cached pages need no enclosure metadata. */ }
			entry.querySelectorAll('.thumbnail img, .text img:not(.icon):not(.favicon)').forEach(img => {
				const width = pixels(img.getAttribute('width'));
				const height = pixels(img.getAttribute('height'));
				if (width && width <= 8 || height && height <= 8) return;
				const variants = [];
				const include = record => { if (record && !variants.includes(record)) variants.push(record); };
				const original = img.getAttribute('data-original') || img.getAttribute('data-src') || img.getAttribute('src');
				include(add(original, width || img.naturalWidth, img));
				// Avoid FreshRSS's grey.gif placeholder when data-original is present.
				const sources = [img, ...Array.from(img.closest('picture')?.querySelectorAll('source') || [])];
				for (const source of sources) {
					for (const attr of ['srcset', 'data-srcset', 'data-original-srcset']) {
						for (const item of (source.getAttribute(attr) || '').split(',')) {
							const match = item.trim().match(/^(\S+)(?:\s+(\d+(?:\.\d+)?)(w|x))?$/);
							if (match) include(add(match[1], match[3] === 'x' ? (width || 1) * Number(match[2]) : Number(match[2]) || 0, img));
						}
					}
				}
				if (variants.length) {
					groups.set(img, variants);
					lead ||= variants[0];
				}
			});
			function related(seeds) {
				const keys = new Set(seeds.map(item => item.key));
				// srcset/picture URLs are variants of the same image even on unknown CDNs.
				let previousSize;
				do {
					previousSize = keys.size;
					for (const variants of groups.values()) {
						if (variants.some(item => keys.has(item.key))) variants.forEach(item => keys.add(item.key));
					}
				} while (keys.size !== previousSize);
				return Array.from(all.values()).filter(item => keys.has(item.key)).sort((a, b) =>
					Number(b.original) - Number(a.original) || b.width - a.width);
			}
			return { cover: lead ? related([lead]) : [], images: Array.from(groups, ([node, variants]) => ({ node, choices: related(variants) })) };
		}
		function useImageVariants(img, choices, isCard = false) {
			if (!choices.length) return;
			let index = 0;
			const pictureSources = Array.from(img.closest('picture')?.querySelectorAll('source') || []);
			function apply() {
				if (index >= choices.length) {
					img.removeEventListener('error', failed);
					if (isCard) img.remove();
					return;
				}
				const url = choices[index].url;
				if (!isCard) {
					img.removeAttribute('data-original');
					if (img.hasAttribute('srcset')) img.setAttribute('srcset', url);
					pictureSources.forEach(source => source.setAttribute('srcset', url));
				}
				img.src = url;
			}
			function failed() { index++; apply(); }
			img.addEventListener('error', failed);
			img.addEventListener('load', () => img.removeEventListener('error', failed), { once: true });
			apply();
		}
		function prepare(entry) {
			if (entry.querySelector(':scope > .ig-card') || !entry.querySelector('.flux_content')) return;
			const header = entry.querySelector('.flux_header');
			const meta = entry.querySelector('.ig-entry-meta');
			const title = entry.querySelector('.flux_header .title')?.textContent.trim() ||
				entry.querySelector('.content h1.title')?.textContent.trim() || 'Untitled article';
			const source = meta?.dataset.source || header?.dataset.websiteName || 'News';
			const nativeTime = entry.querySelector('time');
			const card = element('button', 'ig-card');
			card.type = 'button';
			card.setAttribute('aria-haspopup', 'dialog');
			card.setAttribute('aria-label', `Read ${title}`);
			const media = element('span', 'ig-media');
			const monogram = element('span', 'ig-monogram', source.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 2).toUpperCase() || 'N');
			monogram.setAttribute('aria-hidden', 'true');
			media.append(monogram);
			let hash = 0;
			for (const ch of source) hash = (hash * 31 + ch.codePointAt(0)) | 0;
			media.style.setProperty('--ig-hue', String(Math.abs(hash) % 360));
			const choices = imageVariants(entry).cover;
			if (choices.length) {
				const img = element('img');
				img.alt = '';
				img.loading = 'lazy';
				img.decoding = 'async';
				// Retain native referrer policy restrictions and never send the reader URL.
				img.referrerPolicy = choices.find(item => item.node)?.node.getAttribute('referrerpolicy') || 'no-referrer';
				useImageVariants(img, choices, true);
				media.append(img);
			}
			const body = element('span', 'ig-card-body');
			body.append(element('span', 'ig-source', source), element('span', 'ig-title', title));
			const footer = element('span', 'ig-card-footer');
			const date = element('time', 'ig-date', meta?.dataset.date || nativeTime?.textContent.trim() || '');
			date.dateTime = meta?.dataset.datetime || nativeTime?.dateTime || '';
			footer.append(date, element('span', 'ig-status'));
			body.append(footer);
			card.append(media, body);
			entry.prepend(card);
			entry.classList.add('ig-ready');
			card.addEventListener('click', event => {
				event.preventDefault();
				event.stopPropagation();
				open(entry);
			});
			updateCard(entry);
		}
		function updateCard(entry) {
			const status = entry.querySelector('.ig-status');
			if (status) status.textContent = entry.classList.contains('favorite') ? '★ Saved' :
				entry.classList.contains('not_read') ? '● Unread' : 'Read';
		}
		function discover() { stream.querySelectorAll(':scope > .flux').forEach(prepare); }
		const dialog = element('dialog', 'ig-reader');
		dialog.setAttribute('aria-label', 'Article reader');
		const toolbar = element('div', 'ig-toolbar');
		const previous = button('Previous article (Left arrow)', '←', () => navigate(-1));
		const next = button('Next article (Right arrow)', '→', () => navigate(1));
		const progress = element('span', 'ig-progress');
		progress.setAttribute('aria-live', 'polite');
		const bookmark = button('Save article', '☆', () => { if (active) mark_favorite(active); });
		const read = button('Mark unread', 'Mark unread', () => { if (active) mark_read(active, false, false); });
		const original = element('a', 'ig-control', 'Original ↗');
		original.target = '_blank';
		original.rel = 'noopener noreferrer';
		const closeButton = button('Close reader (Escape)', '×', () => dialog.close());
		closeButton.autofocus = true;
		toolbar.append(previous, next, progress, bookmark, read, original, closeButton);
		const readerBody = element('div', 'ig-reader-body');
		dialog.append(toolbar, readerBody);
		let active = null;
		let returnFocus = null;
		let savedX = 0;
		let savedY = 0;
		let slot = null;
		let originalContent = null;
		let scrollBeforeOpen = null;
		let swipe = null;
		function resetSwipe() {
			swipe = null;
			dialog.classList.remove('ig-swiping');
		}
		// Touch events also work in Safari standalone mode. Only claim a deliberate
		// rightward edge swipe; normal article scrolling and pinch zoom stay native.
		dialog.addEventListener('touchstart', event => {
			resetSwipe();
			if (!dialog.open || event.touches.length !== 1 ||
				!window.matchMedia('(max-width: 840px), (pointer: coarse)').matches ||
				event.target.closest?.('a, button, input, textarea, select, [contenteditable], audio, video, iframe, pre, code, table, [role="slider"]') ||
				window.getSelection()?.isCollapsed === false) return;
			const touch = event.touches[0];
			const left = touch.clientX - dialog.getBoundingClientRect().left;
			if (left < 0 || left > 44) return;
			swipe = { id: touch.identifier, x: touch.clientX, y: touch.clientY, started: performance.now(), locked: false };
		}, { passive: true });
		dialog.addEventListener('touchmove', event => {
			if (!swipe) return;
			if (event.touches.length !== 1) { resetSwipe(); return; }
			const touch = event.touches[0];
			if (touch.identifier !== swipe.id) { resetSwipe(); return; }
			const dx = touch.clientX - swipe.x;
			const dy = Math.abs(touch.clientY - swipe.y);
			if (!swipe.locked) {
				if (dx < -12 || dy > 12 && dy * 1.4 > dx) { resetSwipe(); return; }
				if (dx < 12 || dx < dy * 1.4) return;
				swipe.locked = true;
				dialog.classList.add('ig-swiping');
			}
			if (event.cancelable) event.preventDefault();
		}, { passive: false });
		dialog.addEventListener('touchend', event => {
			if (!swipe) return;
			const touch = Array.from(event.changedTouches).find(item => item.identifier === swipe.id);
			const completed = touch && event.touches.length === 0 && swipe.locked &&
				performance.now() - swipe.started < 1500 &&
				touch.clientX - swipe.x >= Math.min(110, dialog.clientWidth * .24) &&
				Math.abs(touch.clientY - swipe.y) < (touch.clientX - swipe.x) * .65;
			resetSwipe();
			if (completed) {
				if (event.cancelable) event.preventDefault();
				dialog.close();
			}
		}, { passive: false });
		dialog.addEventListener('touchcancel', resetSwipe, { passive: true });
		const entries = () => Array.from(stream.querySelectorAll(':scope > .flux.ig-ready'));
		function sync() {
			if (!active) return;
			const list = entries();
			const index = list.indexOf(active);
			previous.disabled = index <= 0;
			next.disabled = index < 0 || index >= list.length - 1;
			progress.textContent = `${index + 1} / ${list.length}`;
			bookmark.textContent = active.classList.contains('favorite') ? '★' : '☆';
			bookmark.setAttribute('aria-pressed', String(active.classList.contains('favorite')));
			bookmark.setAttribute('aria-label', active.classList.contains('favorite') ? 'Unsave article' : 'Save article');
			read.textContent = active.classList.contains('not_read') ? 'Mark read' : 'Mark unread';
			read.setAttribute('aria-label', read.textContent);
			const url = imageURL(active.dataset.link);
			if (url) original.href = url;
			else original.removeAttribute('href');
			bookmark.disabled = read.disabled = Boolean(context.anonymous);
		}
		function restoreContent() {
			if (originalContent && slot?.parentNode) slot.replaceWith(originalContent);
			originalContent = null;
			slot = null;
		}
		function show(entry) {
			if (active === entry && dialog.open) return;
			resetSwipe();
			const content = entry.querySelector(':scope > .flux_content');
			if (!content) return;
			for (const { node, choices } of imageVariants(entry).images) {
				if (node.closest('.text') && choices.length > 1 && !node.dataset.igImageUpgraded) {
					node.dataset.igImageUpgraded = '1';
					useImageVariants(node, choices);
				}
			}
			const wasOpen = dialog.open;
			if (!wasOpen) {
				savedX = scrollBeforeOpen?.x ?? window.scrollX;
				savedY = scrollBeforeOpen?.y ?? window.scrollY;
				returnFocus = entry.querySelector('.ig-card');
			} else {
				// Keep the dialog in the top layer when navigating between articles.
				// moveBefore is not available on iPhone Safari: close/reopen below.
				dialog.close();
			}
			restoreContent();
			active = entry;
			originalContent = content;
			slot = document.createComment('InoreaderGrid article return position');
			content.before(slot);
			readerBody.append(content);
			entry.append(dialog); // Preserve .closest('.flux') and #stream event delegation.
			root.classList.add('ig-modal-open');
			readerBody.scrollTop = 0;
			sync();
			dialog.showModal();
			window.scrollTo(savedX, savedY);
		}
		function open(entry) {
			if (!entry || active === entry && dialog.open) return;
			const x = window.scrollX, y = window.scrollY;
			if (!dialog.open) scrollBeforeOpen = { x, y };
			toggleContent(entry, document.querySelector('.flux.current'), false);
			scrollBeforeOpen = null;
			// openArticle is synchronous; restore native toggleContent's scroll adjustment.
			window.scrollTo(dialog.open ? savedX : x, dialog.open ? savedY : y);
		}
		function navigate(direction) {
			const list = entries();
			const target = list[list.indexOf(active) + direction];
			if (target) open(target);
		}
		dialog.addEventListener('close', () => {
			// A queued close event from previous/next must not tear down the new reader.
			if (dialog.open) return;
			resetSwipe();
			restoreContent();
			active?.classList.remove('active');
			active = null;
			root.classList.remove('ig-modal-open');
			window.scrollTo(savedX, savedY);
			if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
			requestAnimationFrame(() => { if (!dialog.open) window.scrollTo(savedX, savedY); });
		});
		dialog.addEventListener('click', event => {
			if (event.target !== dialog) return;
			const bounds = dialog.getBoundingClientRect();
			if (event.clientX < bounds.left || event.clientX > bounds.right ||
				event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
		});
		// Capture only reader navigation. Native letter shortcuts continue to work.
		document.addEventListener('keydown', event => {
			if (!dialog.open && event.key === 'Escape' && aside?.classList.contains('visible')) {
				event.preventDefault();
				event.stopImmediatePropagation();
				closeAside();
				return;
			}
			if (!dialog.open) {
				scrollBeforeOpen = { x: window.scrollX, y: window.scrollY };
				setTimeout(() => { scrollBeforeOpen = null; }, 0);
			}
			if (!dialog.open || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey ||
				event.target.closest?.('input, textarea, select, [contenteditable="true"], audio, video')) return;
			if (event.key === 'Escape' && location.hash.startsWith('#dropdown-')) return;
			if (!['ArrowLeft', 'ArrowRight', 'Escape'].includes(event.key)) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			if (event.key === 'Escape') dialog.close();
			else navigate(event.key === 'ArrowLeft' ? -1 : 1);
		}, true);
		stream.addEventListener('freshrss:openArticle', event => {
			const entry = event.target.closest('.flux');
			if (entry?.classList.contains('ig-ready')) show(entry);
		});
		document.addEventListener('freshrss:load-more', discover);
		const observer = new MutationObserver(records => {
			let relevant = false;
			for (const record of records) {
				if (record.type === 'attributes') {
					if (record.target.matches('.flux')) {
						updateCard(record.target);
						relevant = true;
					}
				} else {
					for (const node of record.addedNodes) {
						if (node.nodeType === 1 && node.matches('.flux')) { prepare(node); relevant = true; }
					}
					if (record.target === stream && record.removedNodes.length) relevant = true;
				}
			}
			if (!relevant) return;
			if (active && (!active.isConnected || !active.classList.contains('active'))) {
				if (dialog.open) dialog.close();
			} else sync();
		});
		observer.observe(stream, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
		discover();
	}
	if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
	else init();
	// FreshRSS loads main.js asynchronously; it can finish after our deferred asset.
	document.addEventListener('freshrss:globalContextLoaded', () => {
		if (document.readyState !== 'loading') queueMicrotask(init);
	});
	window.addEventListener('load', init, { once: true });
})();
