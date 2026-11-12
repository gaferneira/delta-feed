# Delta and Names screens

## Objective

Make the daily loop usable in a browser: a Delta page that shows the cards the API returns, and a Names page where reviewing an extracted name takes a few seconds. UX quality is a requirement here, not polish.

## Scope

- In: backend additions the screens need (undo, batch, summary, richer group listing, predicate and value on Delta claims); `/delta` and `/names` pages; Delta and Names links in the navigation with the pending count.
- Out: Feed rework and removal of Today/Earlier/All, Saved, Settings, article detail ("Why this card?"), "I already knew this" (no API), analysis notices on Delta (waiting, model unavailable, budget), landing switch, web fonts (the CSS names DM Sans and Manrope but loads no font file; loading them from Google is a privacy decision for Gabriel).

## Visual reference

The reader mockups canvas. Local copies of the relevant artboards: `Names.dc.html`, `Names-states.dc.html`, `Main.dc.html` (Delta), `Delta-states.dc.html`, `Delta-mobile.dc.html`. Reuse the tokens and shared classes in `frontend/src/styles/global.css`; add new shared classes there, not per-page copies.

## Interaction spec

### Names (`/names`)

Wording was changed after first use (2026-11-12): the buttons are "Track this", "Same as <entity>" and "Ignore"; the tabs are "To review", "Tracked" and "Ignored"; the keys are `t`, `s` and `i`. "It's something new" read as "this is news to me". The text below keeps the original terms.

- Heading as in the mockup. Tabs: Pending (with count), Resolved, Dismissed (`?status=`). Meta line: "N names from M articles · most mentioned first". Above 20 pending names, the "large queue" hint from the states sheet.
- One card per name: name, type chip, "k mentions in n articles", other spellings, the evidence sentence, up to three source articles as links, and how many claims the decision unlocks.
- Default action per card, so most cards are one confirm:
  - similar entities exist: they are listed as radio options, the first is preselected, primary button "Link to <entity>", secondary "It's something new";
  - none exist: "No similar names found.", primary button "It's something new", which creates the entity with the extracted name and type at once. "Edit before creating" opens the name, type and homepage form.
  - "Dismiss" is always the quiet third action.
- Keyboard (ignored while typing in a field, hint bar hidden on touch devices): `↑`/`↓` or `k`/`j` move between cards, `Enter` runs the card's primary action, `l` link, `n` new, `d` dismiss, `1`–`5` pick a candidate, `u` undo the last decision, `?` toggles the key list. The current card has a visible ring and is scrolled into view.
- After a decision the card is replaced in place by a confirmation (what happened, how many mentions) with an Undo button, focus moves to the next card, the counts update, and the change is announced in a live region. Undo is offered for the undo window after a link or create (the comparison job is delayed by that window) and without limit after a dismiss.
- "Create all N with no similar name": a disclosure listing those names, all ticked; untick the odd ones, confirm once, one confirmation with "Undo all".
- Failure: the card stays, with the reason in an error block. A name decided elsewhere meanwhile is removed with a note.
- Empty: "All names are reviewed" with a link back to Delta.
- Resolved tab: name → entity, and whether it was linked, created or matched automatically. Dismissed tab: each name has "Restore", which returns it to Pending.
- Phone width: actions wrap, every target at least 44px.

### Delta (`/delta`)

- Heading and lede as in the mockup; meta line "Newest first".
- When names are waiting: the notice "N names from M articles are waiting for review" with "Review names".
- One card per article: source, published and found times, title linking to the original in a new tab, then one bullet per claim: kind chip (New, Changed, Conflicts, Not sure), "First sighting" chip, entity name, the claim (attribute label muted, then the value), "You knew: …" when a baseline claim matched, and the evidence quote.
- "Not sure" claims sit behind "Show N claims we are not sure about" when the card also has other claims; a card with only "not sure" claims shows them open. More than five bullets collapse behind "+N more".
- Footer: "Also covered by N other articles" when above zero; actions Read original, Mark read / Mark unread, Save / Saved. A read card is dimmed and labelled Read.
- States: no cards while names wait (points to Names), no cards at all (points to Feed), load failure (Try again, Open Feed), end of list, Newer/Older paging.

## Checklist

- [x] T1 Backend: richer `GET /mentions` (articles, counts, candidate type, resolved/dismissed details, most mentioned first), `GET /mentions/summary`, delayed comparison plus `POST /mentions/undo`, `POST /mentions/resolve-batch`, `predicate` and `value` on Delta claims. Exercised on the dev database.
- [x] T2 Frontend: `/names` page per the spec.
- [x] T3 Frontend: `/delta` page per the spec, navigation links with the pending count.
- [x] T4 Checked in headless Chrome against the dev database, signed in, at 1280px and 390px: Delta cards, the names notice and badge, mark read and unread; Names keyboard moves, dismiss and undo, create and undo, edit form, batch create of six names and Undo all, Restore on the Dismissed tab. Linking to a candidate, the error states and the 404 path were checked only against intercepted responses (the dev data has no name with a similar entity). The database ended as it started: 16 entities, 6 pending names.

## Checks

- `make test-backend`, `make lint-backend`, `cd backend && DJANGO_DEBUG=true uv run python manage.py makemigrations --check`
- `make test-frontend`, `make build-frontend`
