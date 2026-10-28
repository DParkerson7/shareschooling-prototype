# Assumptions: map pilot

Choices made while building the West Tennessee + DeSoto County, MS pilot that the brief ([docs/map-pilot/claude-brief.md](docs/map-pilot/claude-brief.md)) didn't spell out. Any of these can be changed.

## Things to decide soon

1. **Search engines are blocked for now.** The brief asks for SEO pages and a sitemap, and they're all built. But every listing is an unconfirmed Draft about a real organization, so each page currently tells search engines not to index it. One setting (`allowSearchEngines` in `data/site.json`) turns indexing on.
2. **Drafts are shown** on the test site with a "Draft" tag, as the brief allows. `showDrafts: false` hides them.
3. **The site banner** now reads "Test site: listings are drafts gathered from public pages and not yet confirmed by the organizations." This replaces the old "Prototype — sample data" banner, because the listings are no longer made up.

## How the site is built

4. **Every page is a real, static page** made by `tools/build_site.py` (Python, nothing to install), as the brief's SEO section asks. This replaced the first prototype's single-page map. Old bookmark links like `#/state/tennessee` no longer work.
5. **Pages exist for all 50 states plus DC, all 95 Tennessee counties and all 82 Mississippi counties.** Non-pilot ones are "coming soon" pages. 21 city pages exist, one for each city that has a listing based in it.
6. **The 4 DeSoto cities named in the brief** (Olive Branch, Southaven, Hernando, Nesbit) all have pages because each has a listing.
7. **The Tennessee map is zoomed to West Tennessee** (plus DeSoto County, MS) so small counties stay readable. The rest of Tennessee is cut off at the map's right edge but listed under "Other Tennessee counties".
8. **County shading** on the state maps uses four steps: 1–2, 3–5, 6–10 and 11+ listings, with the count printed on each county.
9. **Nearby counties** come from the real county borders. DeSoto County, MS also links to Fayette County, TN, as the brief asks, even though they don't share a border.
10. **County maps widen to fit pins just over the line.** For example, Shelby County's map includes a Mississippi tutoring center that also serves Shelby.

## Filters and sorting

11. **The delivery filter is inclusive.** "In person" also shows programs offered both in person and online, and "Online" also shows "Both".
12. **Filters start collapsed** behind a "Filters" button (with a count of active filters) so the sticky bar stays small. They open automatically when the web address already has filters in it.
13. **The result count** ("Showing X of Y listings") counts the main list only, not the "Also available to you" column.
14. **Sort order:** Featured first, then confirmed before "still confirming", then by name. With a zip code: Featured first, then confirmed, then nearest. Listings with no pin go last within their group.
15. **The "No listings here yet for…" note** on county pages lists categories with no local or statewide listing, with a "Suggest a resource" link. Umbrella schools are left out of it in Mississippi.

## Zip search

16. **Zip lookups use the 2020 Census zip areas.** A zip that crosses a county line goes to the county holding most of its land.
17. **A zip outside Tennessee and Mississippi** shows a message that it isn't in the pilot yet, with a link to online options. (The lookup file covers only TN and MS, as the brief specifies.)

## Pages and wording

18. **"Online & Nationwide" is now "Online options".** The pilot data has no Nationwide listings, so that page shows the 14 listings delivered online or both ways.
19. **Statewide listings** appear in "Also available to you" on every county page in their state. HomeLife Academy also gets a pin on the Madison County map, since it's based in Jackson.
20. **The "Umbrella schools" category** is stored with a `name` (like the other 12 categories), not a `label` as the brief's example shows, so the existing code reads it the same way.
21. **The state law sections** on the TN and MS pages remain clearly marked placeholders. There's no real legal information on the site.
22. **"Report an issue"** shows a "not connected yet" message. **"Claim this listing"** opens the List your co-op or tutor page with a placeholder note.
23. **The listing form** checks required fields (organization name, category, state, your email, and the confirmation box), stops bots with a hidden field, and offers the entry as a downloadable file marked Draft. Nothing is sent.
24. **The email signup** is in the footer of every page and inside every coming-soon page. It checks the email address and shows "Thanks! You're signed up. (Test site: signups aren't saved yet.)" Nothing is sent, and there are no tracking pixels.
25. **Listing detail pages** show the full source address, a "Draft (not yet published)" line, and Call / Email / Website buttons when those details exist.
26. **Search data on listing pages** uses `LocalBusiness` when there's a street address and `Organization` otherwise (for example, P.O. boxes).

## Look

27. **The theme uses the brief's five values** (teal, gold, cream, Playfair Display, system font), plus supporting shades in `css/theme.css`. Gold is used only behind dark text. The two lightest map shades use dark numbers so the counts stay readable.
28. **Playfair Display loads from Google Fonts**, the only outside file the site uses.
29. **Sponsor placeholders** stay in the side margins on wide screens and drop below the content on smaller ones.

## Housekeeping

30. **The first prototype's sample listings, Colorado data and placeholder images were removed.** They're still in the git history.
31. **A copy of the Pearsons Creek mockup** sits in this folder on David's Mac (the app copied it in). It's excluded from git and has never been uploaded.
