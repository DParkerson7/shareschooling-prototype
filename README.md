# ShareSchooling — clickable prototype

A static website prototype for ShareSchooling: a map-first guide to homeschool help.
Plain HTML, CSS and JavaScript. No build step, no backend, no accounts, no paid services.

**Everything on the site is sample data.** Every listing is made up and labeled "Example listing".

## What's in the folder

| Path | What it is |
| --- | --- |
| `index.html` | Homepage: US map, zip search, and the State › County › Town drill-down |
| `online.html` | Online & Nationwide listings, filtered by subject, grade or category |
| `about.html`, `book.html`, `list-your-resource.html`, `contact.html` | Other pages |
| `data/listings.json` | **All listings, categories, states, counties and towns.** Edit this to change the content. |
| `data/map.json` | Map shapes (states, plus counties for Tennessee and Colorado). You don't need to edit this. |
| `css/theme.css` | **All colors and fonts.** Change the look here. |
| `css/styles.css` | Layout and components |
| `js/` | The scripts that draw the map, cards and filters |
| `img/` | Placeholder images and the browser-tab icon |
| `tools/topo2svg.py` | Optional: rebuilds `data/map.json` if you add map counties for a new state |

## Run it on your computer

The site loads its data with JavaScript, so open it through a tiny local web server rather than double-clicking `index.html`.

1. Open Terminal in this folder.
2. Run:

   ```bash
   python3 -m http.server 8000
   ```

3. Visit <http://localhost:8000> in your browser. Press `Ctrl+C` in Terminal to stop.

## Put it on GitHub Pages

1. Create a GitHub repository and push this folder to its `main` branch.
2. In the repository, open **Settings › Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**, then choose **`main`** and **`/ (root)`**.
4. Click **Save** and wait a minute or two. The site address (like `https://username.github.io/repo-name/`) appears at the top of that page.

No build step or GitHub Actions workflow is needed. All links use relative paths, so the site works from a project address like `username.github.io/repo-name/`. The empty `.nojekyll` file tells GitHub to serve the files as they are.

## Edit the sample data (`data/listings.json`)

The file has three main parts. After editing, reload the page. If the page says the data didn't load, there is usually a missing comma or quote — paste the file into <https://jsonlint.com> to find it.

### `categories`

The 12 categories. Each has an `id` (used by listings) and a `name` (shown on the site). Keep the `id`s as they are unless you also update every listing that uses them.

### `states`

Only states listed here can be drilled into; every other state shows "coming soon".

```jsonc
{
  "id": "tennessee",           // used in the web address: #/state/tennessee
  "name": "Tennessee",
  "fips": "47",                // US Census state code; connects to the map shape
  "lawBasics": "[Placeholder] ...",
  "counties": [
    {
      "id": "williamson",      // used in the web address
      "fips": "47187",         // US Census county code; connects to the map shape
      "name": "Williamson County",
      "towns": [
        { "id": "franklin", "name": "Franklin",
          "zips": ["37064", "37067"],   // zip search matches these
          "lon": -86.869, "lat": 35.925 } // where the dot goes on the county map
      ]
    }
  ]
}
```

To add a new state, you also need its county shapes in `data/map.json`: add its FIPS code to `keep_states` in `tools/topo2svg.py` and re-run it (instructions at the top of that file).

### `listings`

One entry per resource. Every field:

| Field | What it means | Allowed values / example |
| --- | --- | --- |
| `id` | Unique ID | `"ex-001"` |
| `name` | Name shown on the card | `"Example Co-op of Franklin"` |
| `exampleListing` | Shows the "Example listing" label | `true` |
| `category` | One category `id` | `"co-ops"`, `"tutors"`, … |
| `description` | Short description | text |
| `website`, `email`, `phone` | Contact details | use `example.com` addresses and `555-01xx` numbers for samples |
| `image` | Logo or photo | `"img/placeholder-1.svg"` |
| `reach` | Who it serves | `"Local"`, `"Statewide"` or `"Nationwide"` |
| `location` | Where it's based | Local: `{ "state": "tennessee", "county": "williamson", "town": "franklin" }`. Statewide: `{ "state": "tennessee" }`. Nationwide: `null` |
| `serviceArea` | **Local only.** Where it shows up | `{ "towns": ["tennessee/franklin"], "counties": ["tennessee/davidson"] }` — a county entry means every town in that county. Use `null` for Statewide/Nationwide. |
| `delivery` | How it's offered | `"In person"`, `"Online"` or `"Both"` |
| `agesGrades` | Ages or grades | `{ "label": "Grades K–8", "min": 0, "max": 8 }` — `label` is shown; `min`/`max` drive the grade filter (PreK = `-1`, K = `0`, 1–12 as numbers; `null` for parent-only groups) |
| `subjects` | Subjects (used by the subject filter) | `["Math", "Science"]` |
| `worldview` | Faith-based, secular or inclusive | `"Faith-based"`, `"Secular"` or `"Inclusive"` |
| `cost` | Cost and a note | `{ "type": "Free" \| "Paid" \| "Varies", "note": "text" }` |
| `schedule` | When it meets | text |
| `status` | Trust badge | `"Unclaimed"`, `"Claimed"` or `"Verified"` |
| `lastVerified` | Date shown publicly | `"2026-09-14"` (year-month-day) |
| `featured` | Shows the "Featured" label and lists it first | `true` or `false` |
| `source` | Where the info came from | text |

Where listings appear:

- **Town page:** Local listings whose `serviceArea` includes that town or its county. The "Also available to you" column shows that state's Statewide listings and the Nationwide listings.
- **County page:** Local listings serving that county or any of its towns.
- **State page:** Statewide listings. Those in the "State associations and legal help" category appear under associations; the rest appear as state programs.
- **Online & Nationwide page:** Nationwide listings plus any listing delivered `"Online"`.

## Change the look

Open `css/theme.css`. Every color and font is a named setting at the top (for example `--color-primary`). Change a value and it updates everywhere.

## Credits

Map shapes come from [us-atlas](https://github.com/topojson/us-atlas) (ISC license, see `data/MAP-LICENSE.txt`), based on US Census Bureau cartographic boundary files.
