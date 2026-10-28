# Claude brief: Map clearinghouse, West TN pilot

Prepared Oct 27, 2026 for the ShareSchooling prototype (repo `DParkerson7/shareschooling-prototype`, test site at https://dparkerson7.github.io/shareschooling-prototype). Updated the same day with David's decisions (see the Decisions log). **Hosting stays on the GitHub Pages test site for now.** Build on a branch or the test site only. David approves every publish to a production domain, every send, and every paid service.

## Decisions log (Oct 27, 2026)

| # | Decision | What it changes in this build |
|---|---|---|
| 1 | **"Needs verification" listings show publicly, with a note.** | They render like other listings, with a visible note on the card and detail page: "We're still confirming this listing's details." See section 12. |
| 2 | **Public Faith-based / Secular filter.** | A filter with All / Faith-based / Secular, using `religiousAffiliation`. `Unknown` listings appear only under All. See section 4. |
| 3 | **Umbrella schools get their own category.** | New 13th category id `umbrella-schools` ("Umbrella schools"). There are 4 listings: Gateway Homeschool and Faith Heritage (moved out of associations), plus HomeLife Academy and Titus 2 Academy (new). |
| 4 | **DeSoto County, MS joins the pilot.** | The pilot region is now **West Tennessee plus DeSoto County, MS**. There are 16 new DeSoto/MS listings with `location.state: "MS"`. The map must support a county in a second state. See sections 4 and 10. |
| 5 | **Stay on the GitHub Pages test site.** | No custom domain for now. The domain question is resolved. |

## 1. Purpose

ShareSchooling is a map-first clearinghouse of homeschool resources. Parents drill down from the US map to their state, county, and city (or type a zip code) to find co-ops, tutors, classes, field trips, and support near them.

The pilot covers **West Tennessee plus DeSoto County, MS** (21 West TN counties plus DeSoto, 77 researched listings: 61 TN and 16 MS). Every other state and county stays visible but shows a "coming soon / suggest a resource" state.

Goals for this build:
1. Swap the placeholder data for the pilot dataset (`listings.json`).
2. Build the drill-down map (including the cross-state DeSoto County), zip search, category and faith filters, listing cards, and detail pages.
3. Add free vs. featured listing presentation.
4. Add the "List your co-op or tutor" submission form and email signup. These are front end only; nothing posts anywhere real until David picks providers.
5. Apply the new theme, mobile-first.
6. Generate SEO-friendly county and city pages.

## 2. Data files

- `listings.json`: the canonical dataset, an array of 77 objects (schema below). Copy it into the repo as `data/listings.json` → `listings`, or adapt the loader.
- `listings.csv`: the same data, flattened for spreadsheets.
- Notion database "Listings: West Tennessee pilot" (under the ShareSchooling hub): the working copy David edits. It now includes the DeSoto rows. The JSON is regenerated from research; for now, treat the JSON as the source of truth for the build.
- Every listing is `status: "Draft"`, `claimStatus: "Unclaimed"`, `listingTier: "Free"`, `featured: false`.

### Mapping to the existing prototype

The prototype's `data/listings.json` has top-level keys `_about`, `categories`, `states`, `listings`. Keep `categories` and `states`, and replace `listings` with the new array.

- Category ids match the prototype's existing 12 ids: `co-ops, microschools, hybrid, tutors, classes, support-groups, field-trips, sports, testing, special-needs, curriculum, associations`.
- **Add a 13th**: `{ "id": "umbrella-schools", "label": "Umbrella schools" }`.
- Mark both `TN` and `MS` as pilot states in `states`. MS is live only for DeSoto County (see section 10).
- If any prototype code reads old field names (e.g., a flat `city` or `lat`), update it to the schema below rather than renaming the data.

## 3. Schema and field definitions

| Field | Type | Definition |
|---|---|---|
| `id` | string | Stable slug: `slug(name)-slug(city)`, or `slug(name)-{state}` (e.g., `-tn`, `-ms`) when there's no city. Use it in URLs (`/listing/{id}`). Never regenerate it for an existing listing. |
| `name` | string | Organization or program name as it appears publicly. |
| `category` | string | One of the 13 category ids. |
| `categoryLabel` | string | Display label for the category. |
| `description` | string | 1-2 sentence neutral summary (card text). |
| `reach` | enum | `Local`, `Regional`, `Statewide`, `Nationwide`. **`Regional`** covers multi-county orgs such as WTHEA (still an open question). |
| `location.state` | string | Two-letter state code: `TN` or `MS`. |
| `location.county` | string\|null | Home county, without the word "County". It is in `location.state`. Null for statewide/regional orgs with no fixed base. |
| `location.city` | string\|null | Home city. |
| `location.zip` | string\|null | Only when publicly listed. |
| `location.address` | string\|null | Only public, organizational addresses (never a private home). Often blank on purpose. |
| `serviceArea.counties` | string[] | Counties the listing serves; it shows up on each of those county pages. See "Cross-state counties" in section 4. |
| `latitude`, `longitude` | number\|null | Map pin. Null for statewide listings and for listings with no fixed city. These have no pin and show in the list (or "Also available to you"). |
| `geocodePrecision` | enum\|null | `address` (street geocode), `place` (named landmark/park), `city` (city centroid). For `city`, show the pin as approximate or cluster by city; don't imply an exact location. |
| `delivery` | enum | `In person`, `Online`, `Both`. |
| `website`, `email`, `phone` | string\|null | Organizational contacts only. |
| `agesGrades` | string\|null | Free text, e.g., "K-12". |
| `religiousAffiliation` | enum | `Faith-based`, `Secular`, `Unknown`. Drives the public faith filter. |
| `costNotes` | string\|null | Free text; never invent a price. |
| `sourceUrl` | string | Public page the listing was researched from. Show it on the detail page as "Source". |
| `verificationStatus` | enum | `Likely active` (dated 2025-26 activity found), `Site live (undated)`, `Needs verification`, `Flagged: older source`. |
| `verificationNote` | string | Why that status was given. Internal; don't show it publicly. The public note is the fixed sentence in section 12. |
| `lastChecked` | date | ISO date (2026-10-27). Show it as "Last verified". |
| `listingTier` | enum | `Free` or `Featured`. |
| `featured` | bool | Mirror of tier for quick sorting. |
| `photo` | string\|null | Featured only. |
| `longDescription` | string\|null | Featured only. |
| `status` | enum | `Draft`, `Published`, `Archived`. The site renders `Published` only in production. The test site may show Drafts with a "Draft" ribbon. |
| `claimStatus` | enum | `Unclaimed`, `Claimed`, `Verified`. |

Unknown fields are `null`. Render nothing (not "N/A") when a field is null.

## 4. Drill-down map

- **US view**: all states. Tennessee is highlighted as "Live pilot", and Mississippi as "Pilot: DeSoto County". Other states are muted and clickable; clicking one opens the coming-soon state (section 10).
- **TN view**: county outlines. West TN counties are active and show a count badge or shading by listing count. Middle and East TN counties render as coming soon. Also draw **DeSoto County, MS** as an active county just south of Shelby, as a "Memphis metro" neighbor. It can be a small inset, or the MS county outline drawn across the state line in the same SVG. Label it "DeSoto County, MS" and link it to the MS county view.
- **MS view**: county outlines. Only DeSoto is active; all other MS counties render as coming soon.
- **County view**: county outline, pins for listings with lat/lng, and a list of cards. The list includes listings whose `serviceArea.counties` contains the county, plus that state's statewide listings in a separate "Also available to you" column. The column holds TN statewide listings on TN counties, and MS statewide listings (MS Dept. of Education, Mississippi Home Educators Association) on DeSoto.
- **City view**: local listings first, then the rest of the county, then the "Also available to you" column.
- **Breadcrumb**: `US > Tennessee > Shelby County > Memphis` or `US > Mississippi > DeSoto County > Olive Branch`. Each crumb links back up.
- **Cross-state counties**: key counties internally as `{state}:{county}` (e.g., `MS:DeSoto`, `TN:Shelby`). In this dataset, `serviceArea.counties` holds bare names. Resolve each one to the state where that county is in the pilot: `DeSoto` → MS, every other name → TN. No name collides today. Some listings cross the state line. Mississippi Homeschool Life and Heights Tutorial (MS) also serve Shelby, TN, so they must appear on the Shelby page too. Show a small "MS" or "TN" state tag on any card whose `location.state` differs from the county being viewed.
- **Map shapes**: keep using us-atlas via `tools/topo2svg.py` (already in the repo). Include MS county shapes, or at least DeSoto. City-level drill-down can be a filtered list plus a zoomed county map; no city polygons are needed.
- **Zip search** sits next to the map. Map the zip to its county with a static zip→county lookup bundled as JSON (no paid API), covering TN plus the DeSoto County, MS zips (386xx, e.g., 38632, 38637, 38641, 38651, 38654, 38671, 38672). Then jump to that county view and sort by distance from the zip centroid when lat/lng exists. A zip in any other MS county goes to the MS coming-soon state.
- **Category filter**: chips or a multi-select for the 13 categories. It combines with filters for reach, delivery, and faith. Filters update the pins and cards together and persist in the URL query string (e.g., `?cat=co-ops&faith=secular`).
- **Faith filter (public)**: a three-way control: **All** (default) / **Faith-based** / **Secular**.
  - It filters on `religiousAffiliation`.
  - Listings marked `Unknown` appear **only under All**. They are hidden when Faith-based or Secular is selected, because we haven't confirmed either.
  - Under the control, show a one-line note: "Some listings haven't told us yet. Those appear under All."
  - On cards and detail pages, show a small neutral tag ("Faith-based" or "Secular"). Show no tag for Unknown.
  - Use neutral styling: no icons that rank one choice over the other.
- **Cards**: name, category label, city (plus a state tag when cross-state), a 1-2 line description, a reach/delivery tag, a faith tag (if known), the Featured badge when applicable, the "still confirming" note when applicable (section 12), and a "Last verified" date.
- **Detail page** `/listing/{id}`: all public fields, a small map, the source link, the last-verified date, claim status, a "Claim this listing" link (placeholder), and a "Report an issue" link (placeholder).

## 5. Free vs. featured

- Featured listings get a visible **"Featured"** badge. It is always labeled and never disguised as organic.
- They sort above free listings within the same view and filter, then sort by distance/name.
- Featured detail pages show `photo` and `longDescription`. Free listings show the short description only.
- No payment flow in this build. `listingTier` is set manually in the data. Sponsor/ad areas stay visually separate from listings (page margins), per the website structure page. Featured pricing is still open.

## 6. "List your co-op or tutor" form

- Fields:
  - organization name, category (13 options), description
  - state (TN / MS / Other), city, county (select from the 21 West TN counties plus DeSoto, MS, with a free-text field for others), zip
  - public website, public email, public phone
  - ages/grades, delivery, faith-based/secular/prefer not to say, cost notes
  - submitter name and email (private, never displayed)
  - a checkbox confirming "I represent this organization or it's a public resource."
- **Every submission lands as `status: "Draft"`. Nothing auto-publishes.** David (or a moderator) reviews it before publishing.
- For the pilot, the form writes to a local stub (console or downloadable JSON) or a clearly marked TODO handler. Don't wire it to a live backend, Notion, or email without David's approval.
- Include spam protection that doesn't need a paid service (a honeypot field).
- Include a privacy note: "We publish only organizational contact info. We don't publish home addresses."

## 7. Email signup

- Placement: the footer on every page, and inline on coming-soon pages ("Tell me when [State/County] launches").
- Fields: email (required), state (prefilled from context), optional county, and a checkbox for interests (new listings near me / launch news).
- Front end only: validate, then hand off to a placeholder `subscribe()` function with a TODO. **The provider is still undecided (open question); keep the placeholder.** Show a confirmation message, and add no tracking pixels.

## 8. Theme

Define these CSS variables in `css/theme.css`, replacing the current cream/teal/terracotta/Georgia theme:

```css
:root {
  --color-primary: #1F6F78;   /* teal */
  --color-accent:  #C9A227;   /* gold (Featured badge, highlights) */
  --color-bg:      #FBF4E4;   /* cream */
  --font-heading: 'Playfair Display', Georgia, serif;
  --font-body: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
```

Load Playfair Display from Google Fonts (free). Check contrast: gold on cream likely fails WCAG for body text, so use gold for badges and accents with dark text, not for text on cream. Keep all colors in variables; David expects to tweak them later.

## 9. Mobile-first

- Design for a 375px width first. The map sits on top, with cards in a scrolling list below, plus a sticky filter/search bar.
- Tap targets are at least 44px. On mobile, the map can collapse behind a "Map / List" toggle.
- Detail pages are single column, with tap-to-call and tap-to-email links.
- Keep pages lightweight: inline SVG maps, with no heavy map library required for the pilot.

## 10. Pilot scope and "coming soon"

- The live region is **West Tennessee plus DeSoto County, MS**. Every other state, every non-West-TN county, and every MS county other than DeSoto still has a page with:
  - a **"Coming soon"** message
  - a **"Suggest a resource"** button that opens the listing form with the state prefilled
  - the email signup
- **Statewide listings by state:**
  - TN (TN DOE, THEA, TEL, IEA, Disability Pathfinder, HomeLife Academy, Titus 2 Academy) appear in "Also available to you" on every TN county page, including coming-soon counties.
  - MS (MS Dept. of Education: Home School; Mississippi Home Educators Association) appear on the DeSoto page and on MS coming-soon county pages.
- **Umbrella schools are Tennessee-specific.** Tennessee families can enroll through a church-related (Category IV) umbrella school. Mississippi does not require one, so the DeSoto/MS pages have no umbrella listings. In the MS view, either hide the Umbrella schools chip or show it disabled with the note "Mississippi doesn't require an umbrella school. See the MS Dept. of Education listing."
- HomeLife Academy is pinned at Jackson, TN (city precision; mailing address only), and is also shown statewide. Titus 2 Academy's office is in Columbia (Middle TN), so it has no West TN pin.

## 11. SEO county and city pages

- Static, crawlable routes: `/tn/`, `/tn/{county-slug}-county/`, `/tn/{county-slug}-county/{city-slug}/`, `/ms/`, `/ms/desoto-county/`, `/ms/desoto-county/{city-slug}/` (Olive Branch, Southaven, Hernando, Nesbit), and `/listing/{id}`.
- Each page gets a unique `<title>` and meta description, e.g., "Homeschool co-ops, tutors & resources in DeSoto County, MS | ShareSchooling".
- Each page has an H1 with the place name, a short intro, category sections, and internal links to neighboring counties. Link DeSoto ↔ Shelby (and Fayette) across the state line.
- JSON-LD: `ItemList` on county/city pages and `Organization` or `LocalBusiness` on detail pages (public fields only).
- Generate `sitemap.xml`. GitHub Pages is static, so generate these pages with a small build script from `listings.json`. The site stays on the GitHub Pages test URL for now, so set canonical URLs from a single config value that can change later.
- Thin county pages (no local listings) should still be useful: show regional/statewide resources and the "Suggest a resource" prompt. Don't fill them with filler text.

## 12. Data quality and display rules

- Show "Last verified" on every listing.
- **`Needs verification` listings are shown publicly** (decision 1). They get a visible, neutral note on the card and detail page: **"We're still confirming this listing's details."** Use muted styling (not a warning color). Pair it with the "Report an issue" link. Sort them after confirmed listings within the same featured tier, and don't hide them. There are 8 of these (6 TN, 2 MS).
- **`Flagged: older source`** (1 listing): until David says otherwise, treat it the same way. Show it with the same note.
- `Likely active` and `Site live (undated)` show no note.
- Don't show `verificationNote` publicly; it's internal research context.
- 12 listings have no pin: statewide listings, or groups with no fixed city. Some of these are DeSoto County groups (Mississippi Homeschool Life, DeSoto Diamondbacks, Club Z! Tutoring), which appear in the DeSoto list without a pin.
- City-precision pins share a city centroid. Use clustering or a small jitter so they don't overlap.
- Pilot coverage gaps to show honestly ("Suggest a resource"): DeSoto County currently has no microschool or testing listings.

## 13. Open questions for David

1. **Email provider**: which one (e.g., Buttondown, Mailchimp, ConvertKit)? Nothing gets connected until you pick; the build keeps a placeholder.
2. **Featured price**: what will a featured listing cost, and what does it include?
3. **Homeschool Roster**: it's an existing regional directory (it also covers DeSoto). Should we treat it as a partner, a listing, or a competitor?
4. **Regional reach**: keep "Regional" as a fourth reach level, or fold it into Local with a service area?
5. **Claim outreach**: should we contact orgs to claim and verify their listings? Every message would need your approval first.
6. **Maintenance**: who maintains the listings and reviews submissions, and how often should listings be re-verified (e.g., every 6 months)?
