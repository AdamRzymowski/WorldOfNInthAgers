# The World of Ninth Age Communities

An interactive map for finding local The Ninth Age communities.

1. Choose a country on the world map (or search for it).
2. The country opens in a popup with a logo for each regional community.
3. Click a logo to see its Discord, Messenger, Facebook group, website and other contacts.

It is a static site with no build step, so it can be hosted on GitHub Pages:
**Settings → Pages → Deploy from a branch → `main` / root**.

## Running locally

The page loads its data with `fetch`, so open it through a local web server
rather than by double-clicking `index.html`:

```bash
python -m http.server 8000
```

Then visit http://localhost:8000.

## Adding a community

Edit [`data/communities.json`](data/communities.json). Communities are grouped by
country; the country name must match the name shown in the map tooltip
(for example `United States of America`, `United Kingdom`, `Czechia`).

```json
{
  "countries": {
    "Poland": [
      {
        "name": "Warsaw Ninth Agers",
        "shortName": "Warsaw",
        "region": "Masovia",
        "lat": 52.23,
        "lon": 21.01,
        "logo": "assets/logos/warsaw.png",
        "description": "Weekly games on Thursdays.",
        "links": [
          { "type": "discord", "label": "Join the server", "url": "https://discord.gg/..." },
          { "type": "messenger", "label": "Jan Kowalski" },
          { "type": "facebook", "label": "Warsaw T9A", "url": "https://www.facebook.com/groups/..." },
          { "type": "website", "label": "warsaw-t9a.pl", "url": "https://..." }
        ]
      }
    ]
  }
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Full community name. |
| `lat`, `lon` | yes | Where the logo sits on the country map. Right-click a place in Google Maps to copy its coordinates. |
| `shortName` | no | Label under the logo (defaults to `name`). |
| `region` | no | Shown under the name. |
| `logo` | no | Path or URL to a square image. Put files in `assets/logos/`. Without one, the Ninth Age banner (`assets/banner-logo.webp`) is used. |
| `description` | no | A sentence or two. |
| `type` | no | `Club/Community`, `Store` or `Person`, shown as a tag on the card. |
| `gamingSpace` | no | `true` or `false`: whether there is a place to play. |
| `forumUsername`, `discordUsername` | no | Shown on the card with a Copy button. |
| `links` | no | Any number of contacts, see below. |

Each link has a `type`, a `label`, and optionally a `url`. A link without a
`url` (such as a Messenger name to search for) is shown as text with a
**Copy** button. Known types: `discord`, `messenger`, `facebook`,
`whatsapp`, `telegram`, `instagram`, `youtube`, `website`, `email`,
`contact`, `link`. New types can be added in [`js/links.js`](js/links.js).

## How the map lines up

The artwork is hand-drawn, so its coastlines and borders don't follow real
geography. Hovering and clicking use a **hit map** (`data/hitmap.png`) that
labels every pixel of the artwork with the country it belongs to *as drawn*,
so the highlighted area always matches the lines you can see. Open the site
with `?debug` to see every country's area tinted.

[`tools/build_hitmap.py`](tools/build_hitmap.py) makes it:

1. Splits the artwork into the regions its pen lines enclose, ignoring
   decorations (title, dragons, compass, ships, clouds, sea creatures).
2. Bends real country shapes onto the drawing: a rough fit from the landmarks
   in [`js/calibration.js`](js/calibration.js), then tile-by-tile shape
   matching, then snapping every real coastline and border onto the nearest
   drawn one.
3. Gives each drawn region to the country that covers most of it.
4. Applies [`tools/overrides.json`](tools/overrides.json): hand-checked fixes
   for places where step 3 gets it wrong.

### Fixing a country that's wrong

Render a zoomed, labelled view of the area (artwork pixels, 1774 × 887):

```bash
cd tools
python review_hitmap.py balkans 880 280 1010 390 6
```

That writes `tools/.cache/review/balkans.png` with each country tinted and
named, and a coordinate grid. Then add a fix to `overrides.json`:

- `"regions": [[x, y, "Country"]]` gives the whole drawn region containing
  pixel (x, y) to that country (`null` makes it sea).
- `"areas"` paints a traced outline. With `"mode": "relabel"` only drawn ink
  and land inside the outline change, never open sea; `"mode": "remove"`
  takes a country out of the outline.
- `"merge"` treats one country as part of another where the artwork draws
  them together.

Country names are the ones shown in the map tooltip. Rebuild with:

```bash
cd tools
npm install          # first time only
npm run hitmap       # full rebuild, about a minute
python build_hitmap.py --reuse-warp   # after editing only overrides.json, a few seconds
```

Needs Node, and Python with Pillow and numpy.

### Choices made for disputed areas

The artwork draws Somalia and Cyprus as single countries, so Somaliland and
Northern Cyprus are merged into them. Crimea, drawn as its own small region,
is pinned to Ukraine (the boundary data has it in Russia). Change these in
`overrides.json` if you want something else.

## Country minimaps

A country can have its own ornate map, shown in its popup instead of the
plain outline. Neighbouring countries on it highlight on hover and open when
clicked. Sweden is the first.

To add one (say for Poland):

1. Save the artwork as `assets/country-maps/poland.webp`.
2. Copy [`data/country-maps/sweden.json`](data/country-maps/sweden.json) to
   `data/country-maps/poland.json` and edit it:
   - `highlight`: the featured country and a point (or one per island) inside
     its painted fill. It's found by that colour, so its outline is exact.
   - `regions`: `[x, y, "Country"]`, a point inside each neighbouring country
     as drawn (pixels of the artwork).
   - `water`: a point in each drawn sea.
   - `decorations`: outlines of the crest, compass, ships, frame... so they're
     never clickable.
   - `landmarks`: `[longitude, latitude, x, y]` for a few places, used to put
     community logos in the right spot.
3. Build it, then list it in
   [`data/country-maps/index.json`](data/country-maps/index.json):

```bash
cd tools
python build_minimap.py ../data/country-maps/poland.json --cells
```

`--cells` writes `tools/.cache/minimap-poland-cells.png` with every drawn
region numbered and its coordinates, to help pick the points. The build
warns when a point lands on a pen line or two countries share a region.

4. If the country is painted gold, make it grassy green like the rest, after
   the build (and after `repaint_land.py`, if used):

```bash
python recolour_green.py ../data/country-maps/poland.json
```

The gold version is kept in `assets/country-maps/gold/`; re-running starts
from it, and `build_minimap.py` reads it so the gold detection keeps working.

## Submissions ("plant your banner")

Visitors add themselves from a country's view: the blue plus button turns the
cursor into a waving banner, a click inside the country plants it, and a form
asks for a name, a type (Club/Community, Store or Person), whether there is a gaming space, an optional address (up to 100 characters), at least one of Discord / email / WhatsApp / Facebook, an optional website, optional T9A forum and Discord usernames, an optional comment (up to 200 characters) and an
optional logo (shrunk in the browser to a 256 px square miniature before sending;
without one, the community gets the Ninth Age banner). The code is in [`js/join.js`](js/join.js).

A **Real World View** button under the map swaps the painting for a real
OpenStreetMap view of the country ([`js/street.js`](js/street.js), free, no
key): people can search their town or address and plant on the exact spot.
The address they type goes only to you; the site shows just the banner.

The form is a [Netlify Form](https://docs.netlify.com/forms/setup/) named
`community-submission`: entries, with the planted latitude/longitude and the
logo file, show up under **Forms** in the Netlify dashboard (turn on form
detection there once, and add an email notification if you like). Nothing is
added to the map automatically: copy approved entries into
`data/communities.json`. Sending only works on Netlify, not on a local server.

## Credits

- Country boundaries: [Natural Earth](https://www.naturalearthdata.com/) via
  [world-atlas](https://github.com/topojson/world-atlas) (public domain).
- Brand icons: [Simple Icons](https://simpleicons.org/).
- Built with [D3](https://d3js.org/).
