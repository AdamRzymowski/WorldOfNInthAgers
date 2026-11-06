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

The artwork is hand-drawn, so country shapes are bent to fit it using
landmark points in [`js/calibration.js`](js/calibration.js). Open the site
with `?debug` (e.g. `http://localhost:8000/?debug`) to see the country
outlines in red and the landmarks in blue. If a country's clickable area is
off, add or nudge a landmark there: `[longitude, latitude, imageX, imageY]`,
with image pixels measured on `assets/world-map.webp` (1774 × 887).

## Credits

- Country boundaries: [Natural Earth](https://www.naturalearthdata.com/) via
  [world-atlas](https://github.com/topojson/world-atlas) (public domain).
- Brand icons: [Simple Icons](https://simpleicons.org/).
- Built with [D3](https://d3js.org/).
