# Map pilot handoff (West Tennessee + DeSoto County, MS)

Documentation and draft data for the map-first clearinghouse pilot. These files are not loaded by the site. The prototype still uses the sample data in `data/listings.json`. Do not copy this dataset into that file yet.

| File | What it is |
| --- | --- |
| `claude-brief.md` | Build brief: drill-down map, filters, cards, forms, theme, and SEO pages for West Tennessee plus DeSoto County, MS. |
| `listings.json` | Source of truth for the pilot data. An array of 77 listings (61 in Tennessee, 16 in Mississippi). |
| `listings.csv` | The same 77 listings, flattened for spreadsheets. Row order and ids match `listings.json`. |

Every listing is `status: "Draft"`, `claimStatus: "Unclaimed"`, and `listingTier: "Free"`. Names, descriptions, and organizational contacts were taken from public pages (each listing's `sourceUrl`). Organizations have not claimed or confirmed them.

`claude-brief.md` (section 2, "Mapping to the existing prototype") describes how this `listings.json` array should later replace the `listings` array inside `data/listings.json`. Keep that file's `categories` and `states`, add the `umbrella-schools` category, and mark Tennessee and Mississippi as pilot states. Field names differ from the sample schema (`location.city` rather than `town`, `religiousAffiliation` rather than `worldview`, and so on). Follow the brief and update the loader if needed. That integration is not part of this handoff.
