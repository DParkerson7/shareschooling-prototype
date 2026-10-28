# ShareSchooling: map pilot

A map-first guide to homeschool help. Parents go from the US map to their state, county and city (or type a zip code) to find co-ops, tutors, classes, field trips and support.

The pilot covers **West Tennessee (21 counties) plus DeSoto County, MS**, with 77 listings researched from public pages. Every listing is still a **Draft** that the organization hasn't confirmed, and the site says so in a banner on every page. The build brief is [docs/map-pilot/claude-brief.md](docs/map-pilot/claude-brief.md).

Plain HTML, CSS and JavaScript, hosted on GitHub Pages. No backend, accounts, payments or paid services.

## How it fits together

All pages are generated from the data by a small script, then committed. GitHub Pages serves them as they are.

| Path | What it is | Edit it? |
| --- | --- | --- |
| `data/listings.json` | **All listings**, the 13 categories, and the pilot states and counties | Yes |
| `data/site.json` | Site address, whether Drafts show, and whether search engines may index the site | Yes |
| `templates/pages/` | About, The Book, Contact and List your co-op or tutor pages | Yes |
| `css/theme.css` | **All colors and fonts** | Yes |
| `css/styles.css`, `js/site.js` | Layout and interactive parts (filters, zip search, forms) | Rarely |
| `tools/build_site.py` | Builds every page from the files above | Run it |
| `data/map.json`, `data/zips.json` | Map shapes and zip codes, from free US Census data | No (see "Adding a state") |
| `index.html`, `online.html`, the other top-level pages, `tn/`, `ms/`, the other state folders, `listing/`, `sitemap.xml`, `data/county-routes.json` | **Generated.** Rebuilt every time you run the build | No, they get overwritten |
| `docs/map-pilot/` | The pilot brief and the original research files | Reference |

## Make a change

1. Edit `data/listings.json`, a template, or `css/theme.css`.
2. Open Terminal in this folder and run:

   ```bash
   python3 tools/build_site.py
   ```

   It prints how many pages it built. It needs only the Python that comes with macOS.
3. Preview it (next section), then commit and push to `main`. GitHub Pages updates within a minute or two.

## Preview on your computer

```bash
python3 -m http.server 8000
```

Then visit <http://localhost:8000>. Press `Ctrl+C` in Terminal to stop.

## GitHub Pages

Already on. Settings › Pages is set to **Deploy from a branch**, `main`, `/ (root)`. The test address is <https://dparkerson7.github.io/shareschooling-prototype/>.

If the site moves to a real domain later, change `baseUrl` in `data/site.json` and rebuild. That one value sets every page's canonical address and the sitemap.

## Listing fields (`data/listings.json` › `listings`)

The full definitions are in section 3 of the [brief](docs/map-pilot/claude-brief.md). The ones that change how the site behaves:

| Field | Effect on the site |
| --- | --- |
| `id` | The listing's address: `listing/{id}/`. Never change it for an existing listing. |
| `category` | One of the 13 category ids in `categories`. Drives the category sections and filter. |
| `reach` | `Local`, `Regional` or `Statewide`. Statewide listings show in "Also available to you" on every county page in their state. |
| `location.state` / `county` / `city` | Where it's based. The city decides which city page it appears on first. |
| `serviceArea.counties` | Bare county names. The listing appears on each of those county pages. `DeSoto` means DeSoto County, MS; every other name is in Tennessee. |
| `latitude`, `longitude`, `geocodePrecision` | The map pin. `city` precision shows a lighter "approximate" pin. Leave both `null` for no pin. |
| `religiousAffiliation` | `Faith-based`, `Secular` or `Unknown`. Unknown listings appear only under the "All" faith filter. |
| `verificationStatus` | `Needs verification` and `Flagged: older source` show "We're still confirming this listing's details." and sort after confirmed listings. |
| `verificationNote` | Internal only. Never shown on the site. |
| `lastChecked` | Shown as "Last verified". |
| `listingTier`, `featured` | `Featured` + `true` shows the Featured badge, sorts first, and shows `photo` and `longDescription` on the detail page. |
| `status` | `Draft`, `Published` or `Archived`. With `showDrafts: true` in `data/site.json`, Drafts show with a "Draft" tag; set it to `false` to show only Published listings. |

Empty fields (`null` or `""`) are simply left out on the page.

## Settings (`data/site.json`)

| Setting | Now | What it does |
| --- | --- | --- |
| `baseUrl` | the GitHub Pages test address | Canonical links and sitemap |
| `showDrafts` | `true` | Show Draft listings (with a "Draft" tag) |
| `allowSearchEngines` | `false` | While `false`, every page asks search engines not to index it. Set to `true` when the listings are ready to be found on Google. |

## Adding a state or county to the pilot

1. Add the county names to that state's `pilotCounties` in `data/listings.json` (or add a new state there).
2. For a new state, add its 2-digit FIPS code in `tools/topo2svg.py` and `tools/make_zips.py`, then follow the steps at the top of each file to rebuild `data/map.json` and `data/zips.json`.
3. Run `python3 tools/build_site.py`.

## Credits

Map shapes come from [us-atlas](https://github.com/topojson/us-atlas) (ISC license, see `data/MAP-LICENSE.txt`), based on US Census Bureau cartographic boundary files. Zip codes come from the US Census Bureau 2020 ZCTA files (public domain). Headings use Playfair Display from Google Fonts (free).
