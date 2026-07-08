# 2026 FIFA World Cup Teamsheets

Panini-sticker-album-style teamsheets for all 48 teams at the 2026 FIFA World Cup
(Canada · Mexico · USA). Each team gets one generated poster (`images/<CODE>.png`)
showing all 26 squad members with name, date of birth, age, height, weight,
current club, and EA Sports FC 26 rating, plus a computed team average rating.

This is an unofficial, fan-made concept inspired by the Panini "Road to the World
Cup" sticker album — it is not affiliated with Panini, FIFA, or EA Sports.

## Contents

- `data/teams.json` — all 48 teams: group (A–L), federation name, kit colors, flag colors.
- `data/<CODE>.json` — one file per team with the 26-man squad (final lists as announced 2 June 2026), each player's DOB, height, weight, club, and EA FC 26 overall rating.
- `data/clubs.json` — primary/secondary color pairs for every club appearing in a squad, used to draw the stylized crest chip on each card.
- `generate.py` — builds the HTML for each team and renders it to PNG with headless Chromium (Playwright).
- `images/<CODE>.png` — the finished teamsheet for each team (1500px wide).

## Regenerating

```
python3 generate.py            # render every team with a data file
python3 generate.py BEL FRA     # render specific teams only
python3 generate.py --html BEL  # write the HTML only, skip the screenshot (debugging)
```

Requires Python 3 with `playwright` installed and a Chromium build available
(the script looks for `/opt/pw-browsers/chromium*` first, then falls back to
whatever Playwright has installed).

## Data notes and caveats

- **Player art is a stylized silhouette**, not a photo — real player likenesses
  aren't available to generate. The bust is colored in the team's kit colors
  and carries the player's squad number.
- **Club crests are generic stylized shields** colored in each club's primary/
  secondary colors — they are not the clubs' official logos.
- **"—" means unverified or unconfirmed**, not necessarily unknown. Where a
  player's date of birth, height, weight, or EA FC 26 rating could not be
  confirmed, the field shows a dash rather than a guessed number.
- **Squads reflect the final 26-man lists as announced around 2 June 2026.**
  Injury replacements and any changes after that date are not reflected.
- **Ratings are EA SPORTS FC 26 overall ratings** at time of writing. The team
  average shown on each sheet is computed only over players with a confirmed
  rating (the coverage, e.g. "21/26 rated", is shown alongside it).
- A few squads legitimately carry a non-standard position split (e.g. Egypt's
  26-man list includes 4 goalkeepers) — the sheets render these as-is.
- Shirt numbers use official squad numbers where the source announcement
  included them; otherwise players are numbered 1–26 in goalkeeper → defender
  → midfielder → forward order.
