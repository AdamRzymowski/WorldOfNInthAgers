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
| `logo` | no | Path or URL to a square image. Put files in `assets/logos/`. Without one, a crest with the community's initials is drawn. |
| `description` | no | A sentence or two. |
| `links` | no | Any number of contacts, see below. |

Each link has a `type`, a `label`, and optionally a `url`. A link without a
`url` (such as a Messenger name to search for) is shown as text with a
**Copy** button. Known types: `discord`, `messenger`, `facebook`,
`whatsapp`, `telegram`, `instagram`, `youtube`, `website`, `email`,
`contact`, `link`. New types can be added in [`js/links.js`](js/links.js).

The entries currently in `communities.json` are placeholders marked
"example" — replace them with real communities.

## How the map lines up

The artwork is hand-drawn, so two things make clicks land on the right country:

- **Hit map** (`data/hitmap.png`): every pixel of the artwork is labelled with
  the country it belongs to, *as drawn*. Hovering and clicking use this, so the
  highlighted area always matches the borders you can see. It's built from the
  artwork's own ink lines: each enclosed region goes to the real country that
  covers most of it.
- **Calibration** ([`js/calibration.js`](js/calibration.js)): landmark points
  that bend real geography onto the artwork. The hit map build uses it to
  decide which country each drawn region is. Open the site with `?debug` to
  see the warped real borders in red and the landmarks in blue. Each landmark
  is `[longitude, latitude, imageX, imageY]` in pixels of
  `assets/world-map.webp` (1774 × 887).

If you change the artwork or the landmarks, rebuild the hit map (needs Node,
and Python with Pillow and numpy):

```bash
cd tools
npm install
npm run hitmap
```

## Credits

- Country boundaries: [Natural Earth](https://www.naturalearthdata.com/) via
  [world-atlas](https://github.com/topojson/world-atlas) (public domain).
- Brand icons: [Simple Icons](https://simpleicons.org/).
- Built with [D3](https://d3js.org/).
