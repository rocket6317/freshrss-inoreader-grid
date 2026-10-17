# Editorial screenshot demo

All headlines, publication names and article copy in `articles.json` are fictional. Photos are illustrative stock imagery, not evidence of the events described. No personal feeds, accounts or provider calls are involved, and no endorsement is implied.

The demo uses the actual extension CSS/JavaScript and installed FreshRSS core handlers, with local mock state responses. Eight bundled photos give each article its own image. Everything is served on localhost when generating screenshots; no image hotlinking is needed.

## Photo credits and licence

The following photos remain under the [Pexels licence](https://www.pexels.com/license/), **not the repository's MIT licence**. This also applies to the photographic material incorporated in the screenshots. The downloaded copies are resized to 1280 pixels wide; the interface applies its usual display-only darkening and crops card thumbnails.

| File | Photographer | Original photo |
| --- | --- | --- |
| `images/rooftop-garden.jpg` | Krystian B | [Urban garden rooftop at sunset](https://www.pexels.com/photo/urban-garden-rooftop-at-sunset-with-people-relaxing-37731387/) |
| `images/pottery-workshop.jpg` | Yan Krukau | [Hands of a potter working with clay](https://www.pexels.com/photo/hands-of-a-potter-working-with-clay-6611351/) |
| `images/greenhouse.jpg` | Ryutaro Tsukata | [Plants in a glass greenhouse](https://www.pexels.com/photo/green-plants-growing-in-modern-glass-greenhouse-5472387/) |
| `images/coastal-railway.jpg` | Lindsey Garrett | [Train beside the beach](https://www.pexels.com/photo/a-moving-train-on-track-beside-the-beach-13993407/) |
| `images/shared-supper.jpg` | cottonbro studio | [People enjoying an outdoor dinner](https://www.pexels.com/photo/people-sitting-at-the-table-5961887/) |
| `images/handmade-mug.jpg` | Esma Atak | [White painted handmade mug](https://www.pexels.com/photo/white-painted-handmade-mug-18688172/) |
| `images/window-plant.jpg` | cottonbro studio | [A plant beside an open window](https://www.pexels.com/photo/a-plant-placed-on-the-window-10254323/) |
| `images/coastal-boardwalk.jpg` | Matt Webster | [Coastal boardwalk and ocean outlook](https://www.pexels.com/photo/coastal-boardwalk-view-with-scenic-ocean-outlook-37262992/) |

Licence checked on 17 October 2026. Pexels permits free use and modification; its restrictions still apply. These assets support the interface demo and are not offered as a stock-photo collection.

## Regenerate

With the browser-test prerequisites and a FreshRSS 1.30.1 container available, run:

```sh
.venv/bin/python tests/browser.py --screenshots
```

The browser suite runs first, then captures the editorial demo at desktop, narrow mobile and wider mobile sizes, plus the mobile reader. Mobile screenshots use Chromium emulation, not a physical iPhone.
