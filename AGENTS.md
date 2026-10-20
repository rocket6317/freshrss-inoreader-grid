# InoreaderGrid development context

This repository is a standalone **FreshRSS 1.30.1 user extension**. Read `README.md` and `CONTRIBUTING.md` before making changes. This file preserves project decisions for later development sessions; inspect the current checkout and recent commits for newer changes.

## Architecture and invariants

- `extension.php` registers assets and `entry_before_display`. Normal-view entries receive escaped display metadata and a native bookmark URL. Metadata stays in memory; do not rewrite stored articles.
- `static/grid.js` progressively enhances `#stream.normal` after native FreshRSS functions are ready. `static/grid.css` is scoped to `html.ig-enabled`. Reader and Global views retain native presentation.
- Cards open a native `<dialog>`. Move the **original** `.flux_content` into the dialog inside its original entry/stream ancestry, then restore it. Do not clone article DOM: extension controls, state, and delegated FreshRSS handlers depend on identity and ancestry.
- Reuse native article opening, read/unread, bookmarks, keyboard navigation and pagination. Observe dynamically added articles and native load-more events. Preserve scroll position and keyboard focus when closing.
- Page-local automatic mark-on-scroll and automatic removal of read articles are disabled while the grid is active; saved user preferences must remain untouched. Respect the existing mark-on-open preference.
- Keep the extension self-contained, framework-free and without production dependencies. Disabling it and refreshing must restore the original interface.
- Inspect actual FreshRSS templates, DOM and APIs before changing integration assumptions. Revalidate on version upgrades.

## Agreed interface

- Desktop four-column grid, with intermediate three/two columns and one column on narrow phones; full headlines, feed names, dates and read/saved status.
- Page background `#111111`, neutral charcoal surfaces and grey accents, softened neutral-grey text, understated borders and toolbar, no bright blue or gold accent. Source labels use mixed case; card headline sizes remain unchanged. Current dark-mode image filter is `brightness(.85)`; images are not rewritten.
- Card headline sizes: desktop 15px, at most 600px wide 14px, at most 420px wide 16px. Preserve these choices unless the requested change concerns typography.
- Collapsed feed sidebar with a reachable explicit close control and Escape support.
- Desktop centred reader; mobile full-screen reader with safe-area padding and touch-sized controls. A rightward swipe starting within 56px of the left edge closes the mobile reader. Short quick flicks are recognised separately from deliberate drags; keep the distance, speed and horizontal-intent safeguards. Vertical scrolling, interactive controls, text selection, multiple fingers and horizontal code/table scrolling must remain usable.
- Hide FreshRSS's native bottom arrow bar while enhanced. Preserve previous/next, save, read/unread, original link and close controls in the reader toolbar.
- Select the largest **supplied variant of the same image**, including enclosure, responsive, lazy and picture metadata. Publisher matching includes Echo/Globe patterns. Keep working smaller-image fallbacks; do not invent CDN URLs, scrape publishers, or choose an unrelated larger image. Image-less feeds retain monogram artwork.

## Safety and privacy

- Live deployments can contain independent UserCSS, UserJS, ModernUI, AI Summary, Readability and other extensions. Never overwrite or modify these as part of this extension's work.
- On an existing installation, make a timestamped backup inside the extension directory before changes. Ask before changing files outside the extension, restarting containers or taking destructive actions unless the user has already explicitly authorized that scope.
- Never publish installation-specific paths, account identifiers, feed contents, configuration, backups, credentials, logs or personal author emails. Review an explicit file list before staging/pushing; keep existing no-reply commit identity.
- No telemetry, remote fonts, external scripts, new image proxy or automatic AI calls. Cards can request existing publisher image URLs without a page referrer. Keep real user data out of browser fixtures and external services.

## Tests and demo

- Syntax: `node --check static/grid.js`, `node --check docs/demo/demo.js`, JSON validation for `metadata.json` and `docs/demo/articles.json`, and PHP lint.
- PHP integration: `tests/extension.php` uses real FreshRSS classes and synthetic entries. Set `FRESHRSS_ROOT` when the checkout is not directly inside the application's extensions directory.
- Browser integration: `python3 tests/browser.py` requires Docker, Chromium and `websocket-client`. Override `FRESHRSS_CONTAINER` and `CHROMIUM_BINARY` as needed. Only standard native FreshRSS assets are read; no accounts or real feeds are loaded, state requests are mocked and publisher image fixtures are fulfilled locally.
- `python3 tests/browser.py --screenshots` runs the checks and then captures the separate editorial demo. Eight fictional articles use **eight distinct local stock photos**. The README shows desktop, one-column mobile, two-column mobile and mobile reader screenshots.
- Photo sources and credits are in `docs/demo/README.md`. Code/original text are MIT; photos and photographic material in screenshots retain the Pexels licence. Do not relicense them as MIT. All story/publication names are fictional and photos are illustrative.
- Desktop screenshot: `docs/screenshots/desktop-charcoal.png`. Earlier image URLs displayed stale previews, so use a fresh descriptive filename when replacing a screenshot that remains cached.
- GitHub Actions validates syntax and PHP integration against the FreshRSS 1.30.1 Docker image. Browser coverage currently runs locally.

## Verification limits

Chromium emulation does not verify physical iPhone Safari, home-screen PWA safe areas or system gestures. Authenticated state persistence, real pagination responses, live AI provider calls, compatibility with every extension and a full assistive-technology review remain unverified. Preserve these limitations in reports; do not claim synthetic checks prove live behaviour.
