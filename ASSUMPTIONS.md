# Assumptions

Everything I decided that the build brief didn't spell out. Any of these can be changed.

## Content and data

1. **Example states:** Tennessee (Williamson and Davidson counties) and Colorado (El Paso and Larimer counties). Chosen only to show two different regions; any states can replace them.
2. **Towns and zip codes are real places** (e.g. Franklin, TN 37064; Colorado Springs, CO 80903) so the map and zip search feel realistic. Only the *listings* are made up.
3. **37 example listings**, covering all 12 categories and all three reaches (Local, Statewide, Nationwide). Names all start with "Example", websites use `example.com`, and phone numbers use the reserved fictional range `555-0100`–`555-0199`.
4. **State law basics** are a clearly marked placeholder, not real legal information.
5. **Hero line:** "Join the Education Revolution!" plus one encouraging line I wrote from section 1 of the brief ("You made the right decision…").
6. **Book page and About teaser** use "[book title TBD]" and placeholder text. I didn't invent a title, author or release date.
7. **"Faith-based, secular, or inclusive"** is stored in a field called `worldview` and shown on the site as "Approach".
8. **Ages/grades** are stored as a display label plus a numeric grade range (PreK = -1, K = 0), so the grade filter on the Online page can work.
9. **Location and service area** use the state/county/town ids from the same JSON file, so a Local listing can appear in several towns.
10. **Map shapes live in a second file,** `data/map.json`. The brief's "one JSON file" rule is about listings; all listing, category, state, county and town data is in `data/listings.json`.

## How pages behave

11. **Town page category filter** filters both the local list and the "Also available to you" column.
12. **"Also available to you"** shows all of the state's statewide listings and the top 4 nationwide listings (featured first), with a link to see all.
13. **State page** splits statewide listings into "Statewide associations & legal help" (that category) and "Programs just for [state] families" (all other categories).
14. **Online & Nationwide page** shows Nationwide listings plus any statewide listing delivered online, with a "Nationwide only" option.
15. **Featured listings** are sorted to the top of every list and get a yellow border and "★ Featured" label.
16. **Trust signals:** each card shows a status badge (✓ Verified, ● Claimed, ○ Unclaimed) and "Checked [date]". The detail window explains what each status means.
17. **"Report outdated info"** shows a "not connected yet" message. **"Claim this listing"** goes to a short Claim section on the List Your Resource page (also a placeholder).
18. **Forms** (mailing list, List Your Resource) say on the page that they don't work yet and send nothing.
19. **Clicking a state with no data** opens a friendly "coming soon" page with links to Online & Nationwide and List Your Resource. Counties without data are greyed out and not clickable.
20. **Listing detail** opens as an accessible pop-up window (closes with Esc, the × button or clicking outside) rather than a separate page.
21. **Web addresses** use `#/state/…/county/…/town/…` so every view can be bookmarked and the browser Back button works, with no server setup on GitHub Pages.

## Look and feel

22. **Placeholder palette:** warm cream background, deep teal, terracotta and a sunny yellow for "Featured". **Fonts:** Georgia for headings and the device's system font for text, so nothing extra downloads. All in `css/theme.css`.
23. **Logo** is just the word "ShareSchooling" in text; the browser-tab icon is a simple placeholder shape.
24. **Sponsor placeholders** sit in the left and right margins on wide screens (1280px and up). On narrower screens they move below the content; on phones only one shows.
25. **No dark mode,** since the brand isn't decided yet.

## Technical

26. **No libraries or frameworks at all.** The map shapes were pre-converted from the open us-atlas data into plain SVG outlines, so the site downloads nothing from other websites.
27. **Alaska and Hawaii** appear as small insets in the usual US-map style.
28. **JavaScript is required** for the map and listings (the page says so if it's turned off). The About, Book, List Your Resource and Contact pages work without it.
29. The repo has been set up with git on the `main` branch but **nothing has been committed or pushed**.
