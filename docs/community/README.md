# Community features handoff

Build brief for family reviews and the later community modules on the ShareSchooling map test site. These files are not loaded by the site. David reviews the brief first. Claude implements after that, one module at a time, in follow-up pull requests.

| File | What it is |
| --- | --- |
| `BRIEF.md` | The build brief (November 22, 2026). Reviews are the first phase. Claimed listings, a test-only group portal, state law guides, and the other modules follow. Each module has an on/off flag. Accounts and stored posts go on Render: a free web service plus the smallest paid Postgres plan (about $6 a month), which David approved so the database does not expire. |
| `sample-data.json` | Example records for every module. Not real families, not legal advice, and not a feed the site reads. |

The map itself is described in `docs/map-pilot/claude-brief.md` and `docs/map-pilot/map-navigation-brief.md`. This folder does not change listing research data or generated pages.
