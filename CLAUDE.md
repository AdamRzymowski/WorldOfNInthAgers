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
   location, type (Club/Community, Store or Person), whether it has a gaming
   space, contacts, website, T9A forum and Discord usernames, whether it has a logo, and when it arrived. If there
   are none, say so in one line.
4. Wait for the user to decide on each one: add it to the map, leave it
   pending, or mark it as spam / delete it in Netlify. Don't add, delete or
   mark anything they haven't decided on.
5. Only then push. If the user says to push without reviewing, push and note
   that submissions were not reviewed.

## "Add all pending communities"

When the user says this:

1. Read the submissions and find the ones not on the map yet, as in steps 1–2
   above.
2. Check each against the map and against the other pending submissions for
   likely duplicates. Flag a pair when any of these hold:
   - the names match ignoring case, accents, spaces and punctuation, or are
     nearly the same (one contains the other, or a typo or two apart);
   - they are in the same country within about 25 km of each other;
   - they share a contact (the same Discord invite, email, WhatsApp or
     Facebook link).
3. Add every pending submission that has no flag, without asking again.
4. Don't add flagged ones. List each with what it resembles and why (for
   example "Salamandra, 14 km from the Salamandra already on the map, same
   name"), and let the user choose: add it as a separate community, merge its
   contacts into the existing entry, or skip it.
5. Report what was added, what is waiting on the user, and commit on the
   current version branch. Don't push unless asked.

## Adding a submission

Put it under its country in `data/communities.json` with:

- `name`, `lat`, `lon`;
- `type` and `gamingSpace` (`true`/`false`);
- `region` from its address, if given;
- `description` from its extra comment, if given and it reads as one
  (otherwise just show the comment to the user);
- `forumUsername` and `discordUsername`, if given;
- a link per contact (`discord`, `email`, `whatsapp`, `facebook`) and
  `website` for its website; a value that isn't a link becomes a label with
  no `url`;
- `logo`, if it sent one: download it into `assets/logos/<slug>.webp`.
  Without one the Ninth Age banner is used.

The community card shows all of these.

## Versions and pushing

Work goes on a local `version-X.Y` branch, never straight on `main`. "Push to
local" means commit on that branch only. "Push" means: review submissions
(above), push the version branch and `version-X.Y:main` to `origin`, move
local `main` to it, then create `version-X.(Y+1)` for the next work. Batch
changes: each push to `main` costs a Netlify deploy, and the account's
monthly credit allowance is limited.
