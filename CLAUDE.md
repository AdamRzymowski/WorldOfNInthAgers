# The World of Ninth Age Communities

Static site (no build step) deployed on Netlify as project `t9a-community`
at https://t9a-community.com. Netlify publishes every push to `main`.
See README.md for how the map, minimaps and submissions work.

## Before every push: review pending submissions

Visitors add communities through the "plant your banner" form, which goes to
the Netlify form `community-submission`. Nothing reaches the map until it is
copied into `data/communities.json`. So before any push to GitHub (on every
"push" request, before running `git push`):

1. Open the submissions in the browser pane:
   https://app.netlify.com/projects/t9a-community/forms (form
   `community-submission`, then **Expand all**). If it shows a sign-in page,
   ask the user to sign in there; never enter credentials yourself.
2. Compare them with `data/communities.json`. A submission is on the map when
   that country has an entry with the same name at the same latitude/longitude
   (to 4 decimals).
3. List every submission that is not on the map yet: name, country,
   location, contacts, whether it has a logo, and when it arrived. If there
   are none, say so in one line.
4. Wait for the user to decide on each one: add it to the map, leave it
   pending, or mark it as spam / delete it in Netlify. Don't add, delete or
   mark anything they haven't decided on.
5. Only then push. If the user says to push without reviewing, push and note
   that submissions were not reviewed.

When adding one: put it under its country in `data/communities.json` with
`name`, `lat`, `lon` and a link per contact (`discord`, `email`, `whatsapp`,
`facebook`; a value that isn't a link becomes a label with no `url`). If it
has a logo, download it into `assets/logos/<slug>.webp` and set `logo`;
without one the Ninth Age banner is used.

## Versions and pushing

Work goes on a local `version-X.Y` branch, never straight on `main`. "Push to
local" means commit on that branch only. "Push" means: review submissions
(above), push the version branch and `version-X.Y:main` to `origin`, move
local `main` to it, then create `version-X.(Y+1)` for the next work. Batch
changes: each push to `main` costs a Netlify deploy, and the account's
monthly credit allowance is limited.
