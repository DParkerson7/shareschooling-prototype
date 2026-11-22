# Community features brief for Claude

Prepared November 22, 2026 for the ShareSchooling prototype (`DParkerson7/shareschooling-prototype`, test site at https://dparkerson7.github.io/shareschooling-prototype/).

**This pull request is a brief and a sample data file only.** It does not change site code, generated pages, or listing data. **David reviews this brief first.** After he approves it, Claude implements one module at a time, each in its own follow-up pull request. Nothing goes live on a production domain without David's approval. Hosting of the map stays on the GitHub Pages test site.

This brief sits next to `docs/map-pilot/claude-brief.md` (the West Tennessee plus DeSoto County pilot) and `docs/map-pilot/map-navigation-brief.md` (map navigation). Those builds are already on the test site. This document covers family reviews first, then the other community modules.

Example records live in `sample-data.json` in this folder. The site does not load that file.

## Decisions log (November 22, 2026)

David approved the following. The build follows these rows.

| # | Decision | What it changes |
|---|---|---|
| 1 | **Only a signed-in family with a verified account can post a review.** | Email is confirmed before the first post. Visitors can read published reviews. |
| 2 | **Reviews are on for every listing.** | An organization cannot turn reviews off, including after it claims the listing or pays for a portal. |
| 3 | **Ratings are a few categories, not one star score.** A written comment is optional. | Starter list is in section 6. David can rename or hide a category without a code change. At least one category score is required. |
| 4 | **Public rules sit next to the form.** No children's names, no home addresses, no personal phone numbers or personal emails. Keep it about the group's program. Personal attacks are not allowed. Fair criticism is welcome. | A low rating is not a reason to hold or hide a review. It posts like any other review. |
| 5 | **An automatic filter checks every review on the server.** Clean reviews from accounts past the new-account wait publish immediately. Anything the filter catches is **held for a person**, not rejected. | A moderator can approve, edit out the problem, or remove. |
| 6 | **A new account's first reviews wait in the queue.** | Default is the first 2. After that many reviews have been approved (or auto-published), later clean reviews skip the wait. The number is a setting. |
| 7 | **Families and organizations can flag a live review.** Enough flags hide it until a moderator looks. | Default is 3 flags. Hiding is not deletion. |
| 8 | **Every organization can post one public reply under a review** after it proves it represents that listing. | Claim flow is in section 6. The fuller "keep the listing current" tools are the claims module (section 7). |
| 9 | **Two admin pages: settings and a moderation queue.** A moderator role exists so trusted parents or regional volunteers can help later. | David is the only admin at the start. He grants moderator access; there is no public application. |
| 10 | **Each feature is its own module with an on/off flag.** | Flags live in `data/site.json` and can also be flipped on the admin settings page. Off keeps the data and hides the UI. |
| 11 | **Build order:** reviews, then claimed listings, then the group portal, then state law guides, then the rest (section 4). | The portal is built for testing only. |
| 12 | **Backend is Render: a free web service plus the smallest paid Postgres (about $6 a month).** David approved that database on November 22, 2026, so reviews are not deleted when a free database expires. | The map stays on GitHub Pages. A larger database, a paid web service, extra storage, an email sender, live payments, or a paid workspace plan still need a separate yes. See section 5. |
| 13 | **The group portal is a paid tier for testing only.** Basic listings, reviews, and the map stay free. | Payments run in a provider's test mode, or a "mark as paid" toggle. No real charges. An admin switch can grant the portal without a payment. Pricing is a config value, left unset until David decides. |
| 14 | **Paying does not change how a group is judged or found.** | Portal status does not affect ratings, which reviews are public, moderation, or search and map ranking. The same review rules apply to every listing. |
| 15 | **State law guides are a template plus a data format.** | Claude does not write the legal content. David researches and approves each state. |

## 1. Purpose

Families should be able to comment on and rate the organizations on the map (co-ops, tutors, programs, and the other categories). The first version is a test with a handful of David's friends, before the map goes nationwide. It should be small enough to try in a week of real use, and shaped so more states, more listings, and the later modules fit the same accounts and the same database.

The map stays the point of the site. Community tools hang off a listing, a county, or a state. They do not replace the map.

## 2. How the site is built today

The site is static HTML generated by `tools/build_site.py` and served from the repository root on GitHub Pages. There is no backend, no accounts, and no database. Interactive behavior lives in `js/site.js`. Colors are in `css/theme.css`. Layout is in `css/styles.css`. Listings, categories, and the two pilot state records are in `data/listings.json` (77 listings). Site-wide switches are in `data/site.json` (`baseUrl`, `showDrafts`, `allowSearchEngines`).

GitHub Pages cannot store reviews or sign-ins. Accounts and stored posts need a separate hosted backend. The static pages call that backend from the browser. Secrets stay on the backend, never in this public repository.

| Piece | Where it lives | What reviews and later modules attach to |
|---|---|---|
| Listing cards | `card()` in `tools/build_site.py` | One quiet line of review summary on each card. Cards are also the place for a save button when favorites are on. |
| Card grids | `card_list()` and `category_sections()` | Same card markup everywhere a listing is listed, including "Also available to you". |
| Map preview | Preview markup in `interactive_map()`; pin fields in `listing_pin()`; text filled by `fillPreview()` in `js/site.js` | A short summary (count and category averages). No review text in the popup. |
| Listing page | `build_listing()` | Averages, newest reviews, organization replies, and the claim link that already points at `list-your-resource.html?claim={id}#claim`. |
| Claim placeholder | `templates/pages/list-your-resource.html` and the `claim` query handler in `js/site.js` | Today it only says the claim process is not built. Replace that placeholder when accounts exist. Do not invent a second claim URL. |
| State law box | `build_pilot_state()` prints `lawBasics` from the pilot state in `data/listings.json` | Tennessee and Mississippi currently show a placeholder sentence. The law-guide module replaces that box when a guide is approved. Coming-soon states use `build_other_state()` and have no law box yet. |
| Forms that go nowhere | `subscribe()` and `submitListing()` in `js/site.js` | Both are labeled TODO and do not send. Leave them as they are. Alerts and the portal must not quietly take over the footer signup. |
| Spam honeypot | Hidden `company` field on the signup and listing forms | Reuse the same idea on new forms. |
| Nav | `NAV` in `tools/build_site.py` | Add a link only for a module that is on. Do not add "Reviews" as its own top-level item; reviews live on listings. |
| Generated HTML | `index.html`, `tn/`, `ms/`, `listing/`, other state folders | Do not hand-edit these. Change the generator, `js/site.js` (or a new script it loads), and CSS, then run `python3 tools/build_site.py`. |

Listing ids are stable slugs (`memphis-homeschool-enrichment-cooperative-mhec-memphis` and the rest). URLs are `listing/{id}/`. Never regenerate an id. Every stored review, claim, favorite, event, and portal row points at that id.

Every listing is still `status: "Draft"`, `claimStatus: "Unclaimed"`, and `listingTier: "Free"`. The test site shows drafts on purpose. Reviews apply to drafts during the test, because those are the listings friends will see.

`claimStatus` in the JSON stays the researched value. A live claim is stored in the backend. The listing page reads it and replaces the static "Unclaimed" line. The backend does not commit changes into `data/listings.json`.

## 3. What Claude must not do

- Do not open a new Render account. David already has one. Do not add a payment card or change the card on that account.
- Do not create any paid Render service except the one database he approved: the smallest paid Postgres plan, about $6 a month (section 5). Do not upgrade the web service, add storage, add Redis, or move the workspace to a paid plan.
- Do not sign up for an email sender or a payment company, and do not turn a test payment setup into live mode.
- Do not put the database URL, database password, or API signing secret in the git repo or in the GitHub Pages files. The repository is public. Those values live in the Render web service's environment settings.
- Do not write homeschool legal advice into a state guide. The template can ship empty.
- Do not let a group hide reviews, slow down a low rating, or move itself up the map or the list because it claimed a listing or turned on the portal.
- Do not merge implementation code into the pull request that adds this brief.

`communityApi` in `data/site.json` is the public URL of the Render web service. While that value is empty, dynamic blocks stay hidden and the static map works as it does now. Claude wires the API once David confirms the two Render services exist, or once he has said the implementer may create them on his account. Creating them is the free web service plus the one approved database, and nothing else.

## 4. Modules, flags, and build order

Each feature is a separate module. David can turn one off when it feels cluttered, without deleting the others and without a code change.

### Flags

Add a `modules` object to `data/site.json`:

```json
"modules": {
  "reviews": true,
  "claims": false,
  "groupPortal": false,
  "lawGuides": false,
  "lookingFor": false,
  "events": false,
  "badges": false,
  "favorites": false
}
```

The friends test ships with `reviews` set to `true` and every other flag `false`, as in the block above. Each later pull request turns on only the module it adds.

The generator reads the flags. A flag set to `false` means the build omits that module's nav link, empty mount points, and admin links. Run `python3 tools/build_site.py` after a flag change.

The same keys are stored in backend settings, copied from `data/site.json` the first time the backend runs. The admin settings page can turn a module off later. The browser checks the backend before it draws a review form, a portal link, and so on. If the backend says off, the block stays hidden even if the page was built with the flag on. If the backend is unreachable, dynamic blocks stay hidden. The map still works.

Turning a module off does not delete its rows.

### Build order

Build them in this order. Later modules reuse accounts, the filter, and the queue. They do not get their own user tables.

| Order | Module | Flag | Why this spot |
|---|---|---|---|
| 1 | Family reviews, accounts, admin, and the small "prove you represent this listing" step replies need | `reviews` | The friends test. Everything else hangs on these accounts. |
| 2 | Claimed listings | `claims` | Organizations keep open spots, meeting days, costs, and contact current. |
| 3 | Group portal (test payments only) | `groupPortal` | Only a claimed listing can turn this on. It is a private tool for the group, not a change to the public map. |
| 4 | State law guides | `lawGuides` | David asked for this beside the early work. It does not need the moderation queue. It is a template and a data file, not legal writing. |
| 5 | "Looking for" posts | `lookingFor` | Same filter and queue as reviews. Useful once a few families have accounts. |
| 6 | Local events calendar | `events` | Same moderation, plus a light presence on the county map. |
| 7 | Trusted family badges | `badges` | Uses the approved-review count that phase 1 already stores. Worth turning on after a few reviews exist. |
| 8 | Saved favorites and alerts | `favorites` | Saving is small. Email alerts wait on an email sender David has not chosen. |

Law guides can be built in parallel with claims if David wants the writing template sooner. Do not start the portal before claims, because the portal requires a verified claim.

### How to keep them separate

- One new script per module, for example `js/community/reviews.js`, `js/community/claims.js`, `js/community/portal.js`. `js/site.js` loads a module's script only when that flag is on. Shared sign-in can live in `js/community/account.js`.
- One set of API routes and tables per module, called only by that script.
- Shared pieces, used by every module that needs them: accounts, roles, the word filter, the moderation queue, and settings. Build those once in phase 1.
- New CSS uses the variables already in `css/theme.css`. Gold (`--color-accent`) stays for small badges, not for body text on cream.
- New blocks have to fit a phone. The map brief's bar for no sideways scrolling is 360px, 390px, and 430px. Review text, the portal, and admin tables wrap inside that width.

## 5. Accounts, roles, and backend

All modules share one account system and one database.

### Accounts

- A person signs up with an email and a password. Skip magic-link login for now: the free Render service cannot send that mail, and an email sender is not approved yet.
- The account cannot post until the email is verified. That is the "verified account" rule. Until David approves a sender, he uses "Mark this email verified" on the admin page after the friend signs up with the invite code.
- Display name is a family name ("The Chen family") or a first name and last initial ("Alex P."). It is not an email address and it is not a child's name. The form says so.
- Children do not get accounts.
- One person can hold more than one role. A parent who also runs a co-op is both `family` and `organization`.

| Role | Who | Can |
|---|---|---|
| `family` | A verified parent | Post and edit their own review, flag, and use whichever later modules are on. |
| `organization` | A verified claim on a listing | Reply to reviews on that listing. Edit listing details when `claims` is on. Open the portal when `groupPortal` is on and the listing is granted premium. |
| `moderator` | Granted by an admin | Work the queue: approve, edit, or remove held and flagged items. Cannot change settings or grant roles. |
| `admin` | David | Everything a moderator can do, plus settings, invite code, role grants, premium grants, and removing an account. |

There is no public moderator signup in this build. The admin account page has a control, "Make moderator", on a trusted family account. The badge module explains who counts as trusted. Until that module is on, David can still grant the role by hand.

### Sign-up spam protection

The friends test is invite-only.

- `inviteRequired` defaults to true. David copies a single invite code from the admin settings page and sends it himself (email or text). The site does not email the invitation. Friends enter the code on the sign-up form.
- Verified email, as above.
- A honeypot field, same pattern as the existing forms (a hidden field that must stay empty).
- The server limits how often one IP or one email can create accounts and posts. A plain limit is enough (for example a handful of sign-ups per hour).
- That limit, the honeypot, and the invite code are enough spam protection for a handful of friends. Do not add a paid anti-bot product, and do not add Cloudflare Turnstile unless David asks for it.

When David is ready for open sign-up, he turns `inviteRequired` off in settings. The other protections stay.

### Where the backend must run the sensitive steps

The filter, the new-account hold, flag counts, role checks, claim verification, and "mark as paid" run in the Render web service. The browser never holds the database password, so a family cannot skip those checks by talking to Postgres directly.

The static site and the API are different hosts. Sign-in uses a token the browser stores, not a cookie that assumes the API and the site share a host.

County and city pages ask for **summaries** for the listing ids on that page (count and averages only). The listing page asks for the newest reviews. Do not download every review to draw the map. The map files themselves stay on GitHub Pages, so Render is not serving the HTML, the SVG, or the listing JSON.

### Backend: Render

David chose this on November 22, 2026. Prices below were taken from Render's pricing page that month. Before creating the database, confirm the smallest paid Postgres plan is still about $6 a month. If the price has changed, stop and ask him.

Use his existing Render account. Stay on the **Hobby** workspace ($0). Do not move the workspace to Pro (about $25 a month) or any higher workspace plan.

Two services, in the same region, and no others:

| Service | Plan for the friends test | What it is |
|---|---|---|
| Web service | **Free** ($0). About 512 MB of RAM. | A small HTTP API. Python is a natural fit, because the repo already builds the site with Python. The GitHub Pages pages call this API. |
| Postgres | **Smallest paid plan**, about **$6 a month** (256 MB of RAM, 100 connections). This is the one spend David approved. | Accounts, reviews, claims, and every later module. It does not expire. |

Do not create the free Postgres plan. A free Render database expires 30 days after creation, has no backups, and is then deleted after a short grace period. That is the wrong place for family reviews.

The free web service is enough for a handful of friends, with two limits they will feel:

- It spins down after 15 minutes with no requests, and the next request takes about a minute to wake. The page should say it is waking the server, not show a hard error.
- The workspace includes 750 free hours a month, counted only while the service is awake. A quiet friends test stays inside that. A service that is busy all month can be suspended until the next month.

Its disk is wiped on spin-down and on every deploy. All stored data goes in Postgres. Do not put a SQLite file or uploads on the web service disk.

The database URL (the private URL, since a free web service can reach a database in the same region) and the API signing secret go in the web service's environment settings. `communityApi` in `data/site.json` is only the public `https://` URL of the web service.

Hobby includes about 5 GB of outbound bandwidth a month, then about $0.15 per extra GB, and a card will be on the account because of the database. API replies are small if the map stays on GitHub Pages. If the dashboard shows bandwidth climbing toward that included amount, tell David before the overage. Do not "fix" it by upgrading the workspace unless he says so.

The free web service cannot send mail on the usual SMTP ports. Verification for the friends test is the invite code plus a control on the admin page, "Mark this email verified," so a friend is not stuck waiting for mail the server cannot send. Real verification email, announcement email, and alert email wait until David approves a sender (section 13). Do not upgrade the web service just to send mail.

#### How this grows when the map goes nationwide

Keep the same two services and move each one up a plan when it is actually tight. Each step below costs more and needs David's yes before anyone clicks upgrade. Check Render's pricing page again at that time; these are the November 2026 steps.

| When | Change | About the cost |
|---|---|---|
| Friends test (now) | Free web service + smallest paid Postgres | About $6 a month. Already approved. |
| Families are using it often enough that the one-minute wake, or the 750 free hours, gets in the way | Move the **web service** to the smallest paid plan (about 512 MB, stays awake) | About $7 a month on top of the database. Not approved yet. |
| The database is short on memory, or connections are pegged at 100 | Move **Postgres** to the next plan (about 1 GB of RAM, still 100 connections) | About $19 a month, instead of $6. Not approved yet. |
| Later, if that is still tight | Next web step is about $25 a month for 2 GB. Next database steps are about $40 a month (2 GB) and about $55 a month (4 GB). Extra database storage is about $0.30 per GB a month. | Ask each time. |

Do not add a second database, a Redis / Key Value instance, a persistent disk, or a second web service as a shortcut around asking. The group portal's test payments (section 8) do not change this hosting plan.

#### Considered and not chosen

Supabase and Cloudflare Workers were looked at and set aside. Supabase's free project can pause after a quiet week, and its paid plan starts around $25 a month. Cloudflare's free tier does not pause, but it has no built-in accounts, so sign-in and email would be extra work. David's Render account is the one to build on. Do not set up either alternative.

## 6. Phase 1 — Family reviews

Flag: `reviews`. This is the friends test.

### Who can post

A signed-in family with a verified email. An organization does not review its own listing. A visitor who is not signed in sees a short line: "Sign in to leave a review." One review per account per listing. Saving again updates that same review; it does not add a second score.

### Categories

Starter list, stored as settings so David can change labels without a deploy of new code:

| Id | Label |
|---|---|
| `welcoming` | Welcoming to new families |
| `organized` | Well organized |
| `communication` | Clear communication |
| `worth-it` | Worth the time and cost |

Each score is 1 to 5: Poor, Fair, Good, Very good, Excellent. The family can leave a category blank. At least one score is required. The comment is optional and can be empty.

David can rename a label, hide a category, or add one from the admin settings page. Hiding stops new scores for that category. Old scores stay in the average until he asks to drop them. Do not delete a category id that already has scores.

There is no overall star, and no average of the averages presented as a single score.

### Rules shown on the form

Show this next to the form, in plain text:

> Keep it about the group's program.
> - Don't include children's names.
> - Don't include home addresses, personal phone numbers, or personal emails.
> - Fair criticism is welcome. A low rating is posted like any other review.
> - Personal attacks aren't allowed.

### Filter

The server runs the filter on every new review and every edit. It is a pattern check and a word list, not a paid AI API.

Hold the review (do not publish it) when any of these are on and they match:

- **Name check** (`nameCheck`, default on). A likely personal name: a capitalized two-word name that is not the organization's name, or a phrase like "my son Sam" / "my daughter Sam". False alarms are acceptable, because a person will look.
- **Address check** (`addressCheck`, default on). Something that looks like a street address, a private email, or a phone number.
- **Harsh-language check** (`harshLanguageCheck`, default on). A short word list David can edit in settings. Match whole words, not pieces of harmless words.

A score of 1 is not a hold reason. Do not add a rule that holds "negative" reviews.

Each held review stores why (`new-account`, `possible-name`, `address`, `phone`, `email`, `harsh-language`). The queue shows that reason.

### New accounts

`newAccountHoldCount` defaults to 2. The account's first two reviews go to the queue even when the filter is clean. A review that a moderator approves, and a review that auto-publishes, both count toward the number. After the account reaches that count, a later clean review publishes immediately.

The author sees: "A moderator will look at this before it appears. New accounts wait for the first couple of reviews. A review also waits if it may include a name, an address, or harsh wording. A low rating is not a reason to wait."

Phase 1 stores `approvedReviewCount` on the account. The badge module reads that same number later. Do not invent a second counter.

### Flags

The author of a review does not flag it. Any other signed-in family, and a verified organization on that listing, may flag it once. A second flag from the same account does not count.

`flagsToHide` defaults to 3. At that number the review's status becomes `hidden`. It leaves the public page and appears in the queue. It is not deleted. A moderator can publish it again or remove it.

With only a few friends, 3 flags will be rare. That is intentional. The test plan has David set the number to 1 or 2 long enough to see a review hide, then set it back.

### Status values

`published`, `held`, `hidden`, `removed`.

The public site shows `published` only. Averages and counts use `published` only.

### Edits and removals by the author

The author can edit or delete their own published review. An edit runs through the filter and the new-account rule again. If the edit must wait, the previous published text stays up until a moderator approves the new text. A delete sets status to `removed` and drops it from the averages.

### Organization replies

A verified organization can post one public reply under any published review of its listing. It can edit that reply. The reply runs through the same filter. A held reply is not shown; if an edit is held, the previous public reply stays up.

The organization cannot delete the review, cannot answer a review that is still held, and cannot see the queue.

### Proving the organization represents the listing

This small claim is part of phase 1 so replies work. The claims module (section 7) adds the public "updated" line and the editor. Use one claim record, not two systems.

The existing listing page already links to `list-your-resource.html?claim={id}#claim`. Build the real flow there.

1. The person is signed in.
2. They confirm they represent the organization.
3. Prove it in the first way that works:
   - If the listing has a public `email`, send a short code to that address.
   - Otherwise, if it has a `website`, send a code to an email address at that site's domain.
   - Otherwise, or if the person cannot reach that inbox, the claim waits in the admin queue and David marks it verified. Many listings have a blank email on purpose. Manual approval has to be a normal path, not an error.
4. Status uses the values already in the data: `Unclaimed`, then `Claimed` (asked, not yet proven), then `Verified`.
5. Only `Verified` can reply, and only `Verified` can use the claims editor or the portal later.

Codes expire. David can revoke a verification. Revoking removes the reply button and, when those modules are on, the editor and the portal. It does not delete reviews.

Show "Claimed by the organization" on the listing page only when the claims module is on. In phase 1 the static claim line can stay as it is, and a verified user simply sees "Reply" under reviews.

### How reviews show

**Map preview** (`fillPreview`): under the existing city / category lines, one compact line such as "4 reviews · Welcoming 4.5 · Organized 4.0". Skip a category nobody has scored. If there are no published reviews, add nothing. Do not show "0 reviews". The preview stays free of comment text. "View details" still opens the listing.

**Listing card** (`card()`): one line, "4 family reviews", plus the same averages if they fit on a phone without sideways scrolling. The line links to the listing. No comment text on the card. No line at all when the count is zero or the module is off.

**Listing page** (`build_listing()`): a heading "Family reviews", the count, and the average for each category that has at least one score (one decimal is enough). Then the newest published reviews, 10 at a time, with a "Show more" control. Each review shows the display name, the date, the scores that were given, the comment if there is one, and the organization reply underneath if there is one. Empty state: "No family reviews yet."

Do not show the author's email. Do not show held reviews to the public. The author can see their own held review with the waiting message.

Pin JSON (`listing_pin()`) does not need to carry every score. The preview can fill the summary from the county summary request. Until that request returns, leave the summary line off.

### Admin settings page

A signed-in admin opens an Admin link in the header. Moderators see the queue link and not the settings link. Everyone else sees a short "You need an admin account." Do not rely on a secret URL. A page at `admin/index.html` is fine if the API checks the role.

Settings David can change without a code change:

| Setting | Default | What it does |
|---|---|---|
| `nameCheck` | on | Hold reviews that look like they name a person. |
| `addressCheck` | on | Hold street addresses, personal emails, and phone numbers. |
| `harshLanguageCheck` | on | Hold the editable harsh-word list. |
| Harsh-word list | a short starter list | Add or remove words. |
| `newAccountHoldCount` | 2 | How many approved reviews an account needs before clean reviews skip the wait. |
| `flagsToHide` | 3 | How many flags hide a live review. |
| `inviteRequired` and the invite code | on | Friends-test gate. |
| Mark email verified | admin action | Used until a mail sender exists. Not a substitute for the invite code. |
| Rating categories | the four above | Rename, hide, or add. |
| Module flags | as in `data/site.json` | Hide a module without a rebuild. |
| `trustedBadgeAfter` | 3 | Used when badges are on. Stored now so the setting has a home. |
| Portal price fields | empty | See section 8. Leave them empty. |

### Moderation queue

One queue for held reviews, hidden (flagged) reviews, held replies, and claims waiting for David. Later modules add their held posts to this same queue, marked with a type, rather than building a new admin site.

Each row shows: type, listing name, author display name, how new the account is, approved-review count, the text, the scores, the hold reasons or the flag count, and the time.

Actions:

- **Approve** publishes it and counts it toward the author's approved-review total when it is a review.
- **Edit** lets the moderator cut the problem (a name, a phone number) and then approve. Keep the previous text on the record so David can see what changed.
- **Remove** sets status to `removed`. Optional short note stays internal. The author can see that it was removed. The public page does not show it and does not say why.

A low score is never listed as a hold reason and is not a reason to remove.

### Acceptance for phase 1

- A friend can join with the invite code. David marks the email verified, and the friend can post.
- A clean review from an account past the wait appears on the listing page, the card, and the map preview without a reload of the generator.
- A brand-new account's first two reviews wait in the queue even when the text is harmless, including a review whose scores are all 1.
- A review with a phone number or a child's name waits in the queue, and a moderator can delete that part and approve the rest.
- Three flags (or whatever the setting is) hide a live review until a moderator acts.
- A verified organization can reply. An unverified person cannot.
- Turning `reviews` off hides the form, the card line, and the preview line. The map and the listing text are unchanged.
- No service secret is committed.

## 7. Phase 2 — Claimed listings

Flag: `claims`. Builds on the verified-claim record from phase 1.

A verified organization keeps its own listing current. Families should see fresh practical details instead of only the research snapshot.

### What the organization can edit

- Open spots (short text, such as "A few Thursday spots left" or "Full")
- Meeting days (short text)
- Cost notes (the existing `costNotes` idea; never invent a price)
- Public contact: website, organizational email, organizational phone
- The short public description

### What stays locked

Research fields stay ShareSchooling's: `sourceUrl`, `verificationStatus`, `verificationNote`, `lastChecked`, category, the pin, and `listingTier` / `featured`. The organization does not flip itself to Featured and does not move its pin to a home address.

### Last updated

When they save, store `lastUpdated` (a date) and show **"Updated Nov 18, 2026"** on the listing page and on the card. Keep the existing **"Last verified"** line. The two dates mean different things: last verified is when ShareSchooling checked the public sources; updated is when the organization last saved.

If they have never saved, show no "Updated" line. Do not copy `lastChecked` into it.

### How saves work

Edits live in the backend as an overlay. The page draws `data/listings.json`, then replaces the editable fields when an overlay exists. A rebuild of the static site does not wipe the overlay.

Open spots, meeting days, and cost notes publish on save. Description and contact run through the address and phone filter. If the filter catches them, the previous public text stays up and the new text waits in the queue. Ordinary wording does not wait for David.

### Public label

On a verified listing, the claim row reads "Claimed by the organization." `Claimed` but not yet `Verified` stays "Unclaimed" on the public page so a half-finished request does not look official.

### Acceptance

- After verification, the organization can set open spots and meeting days and the listing page shows them and an Updated date.
- A home address in the description does not replace the public text; it shows up in the queue.
- `claims` off: the editor and the Updated line disappear. Phase 1 replies still work.
- Claiming does not change the card's sort order, the pin, or the reviews.

## 8. Phase 3 — Group portal (testing only)

Flag: `groupPortal`. This is a private area for one group. It is the only paid tier in this brief, and **this phase does not take real money.**

Basic listings, reviews, and the map stay free. A group that has a **verified** claim may turn on a Group portal to run the group through ShareSchooling: a member roster; sign-ups for classes, field trips, and semesters; dues and class fees; a group calendar and announcements; waitlists that fill open spots; and a parent volunteer / teaching rotation.

### Paid status never changes the public listing

State this in the code comments that touch sorting, reviews, and the portal grant, not only in this brief:

- Portal status does not change rating averages, review counts, or which reviews are public.
- Portal status does not change moderation. The group cannot hold a low rating, cannot turn reviews off, and cannot remove a review. They keep the same reply and the same flag as any other verified organization.
- Portal status does not change search, filters, map order, pin size, pin color, or the results list. It is not a sort key.
- Do not set `featured` or `listingTier` from the portal. Featured stays the separate, hand-set label from the map brief.
- Do not put a "premium", "paid", or "portal" badge on the public card, the map preview, or the public listing page during this test. Inside the group's own tools, a small line "Portal on (test)" is enough.

A free unclaimed listing and a portal group use the same review form and the same filter.

### Who can open it

The listing needs a verified claim. The portal then needs a premium grant from one of these sources:

| Source | When to use it |
|---|---|
| `admin-grant` | David turns the portal on for a friend's group from the admin page. This is the normal path for the friends test. |
| `mark-as-paid` | The organizer presses "Mark as paid (test)". Nothing is charged. The row records that the payment was simulated. |
| `stripe-test` | Only if David has created a Stripe account and told Claude to use **test mode**. A test card payment. No real charge. |

The admin page lists claimed listings with a switch, "Grant group portal (test)", and a way to turn it off. Store who granted it and when. Turning it off hides the tools and keeps the roster, sign-ups, and schedules so turning it back on restores them.

The organizer sees "Turn on group portal (test)" only after the claim is verified and the module flag is on. If David has not set a price, the screen says: "Pricing isn't set yet. This test won't charge you."

### Pricing (decide later)

Leave the numbers empty. Do not invent a price.

| Setting | Default | Meaning |
|---|---|---|
| `portalMonthlyFeeCents` | null | Flat monthly fee for the portal itself, if David later wants one. |
| `portalDuesCutPercent` | null | Optional small share of member dues and class fees, if David later wants one. |

Either, both, or neither. The fee model options to show him in the settings screen, as labels next to empty fields, are:

- a flat monthly fee for the group, and/or
- a small cut of dues and class fees collected through the site

When a test payment is recorded and a percent is set, show the arithmetic as a test record only, for example a $40 dues mark with a 3% setting displays "Test record: $40.00 dues, $1.20 platform share (not collected), $38.80 to the group." When the percent is null, the platform share is "not set" and the whole amount is "not collected." No bank transfer, no Stripe Connect, no payout to the group in this phase. Connect and real payouts move real money and need a later decision from David.

The existing "Featured placement" sentence on `list-your-resource.html` is a different open question. Do not fill it in with the portal price.

### Payments

Default for the friends test: **mark as paid**, plus the admin grant. That is enough to test dues, class fees, and the portal switch with no payment company at all.

Stripe, only if David asks:

- Test mode only. Test keys stay in test mode. Do not switch the dashboard to live mode, do not create a live key, and do not point a live webhook at the site.
- The secret key lives on the backend. It is never in git and never in the GitHub Pages JavaScript. The publishable test key may be in the page.
- Use a test card. Do not ask friends for real card numbers.
- Claude does not create the Stripe account, does not enter bank details, and does not "activate" the account for live charges.
- A test-mode payment marks the same `paid-test` state as "mark as paid". The member and the organizer can both see that it was a test.

If Stripe is not configured, hide the card form and keep the mark-as-paid button. Do not block the rest of the portal on Stripe.

### Roster and sign-ups

Private to that group's organizers and members. Never rendered on the map, the listing, a review, search, or a public event.

- Members are existing family accounts. The organizer invites by email address. Until a real email sender is approved, the organizer copies an invite message and sends it themselves. When that person signs in with that email, they join the roster.
- Roles inside the group: `organizer` or `member`. Organizers manage the roster, offerings, announcements, and the rotation. Members sign up and look at the schedule.
- A child record is optional and private: first name and grade, attached to the parent's account. No last name, no home address, no child login. Child names never appear outside the portal.

An **offering** is a class, a field trip, or a semester (`kind`: `class`, `field-trip`, `semester`). It has a title, dates, a capacity, and a fee in cents (0 if free).

Sign-up fills seats in order. When the capacity is reached, the next sign-up is waitlisted with a position. When a seat opens (someone drops, or the organizer raises capacity), the first waitlisted member is enrolled automatically and sees "You're in." If the offering has a fee, their payment state becomes `due` and they use mark-as-paid or a test payment. The seat moves first, then the payment is due, so the waitlist is visible even before anyone pays. This is test behavior. Do not hold the seat for a card authorization in this phase.

### Group calendar and announcements

The group calendar is private. It is not the public events module in section 11. An organizer can later choose "Also show on the public calendar" for a single item; that creates a public event which then follows the public event rules. The default is private.

An announcement has a title, a body, and an audience of all members or one offering. Sending it, in this test, writes a row each member can open inside the portal ("Messages"). It does not send email unless David has approved an email sender. Label the button "Send announcement (test outbox)" so a test run cannot be mistaken for mail that left the site.

Run the announcement through the same address and child-name filter before it reaches the outbox. A hit holds it for the organizer (and shows it in the admin queue) until the problem is edited out. Do not put a child's name or a home address in an announcement.

### Rotation

A list of dates. Each row has a role and one adult member. Starter roles the organizer can rename: Teach, Assist, Snack, Cleanup. Assign parents only, never a child record. A simple list by date is enough. No drag-and-drop requirement.

### Acceptance

- Admin can grant the portal to a verified claim, and the organizer can open the roster, with no payment company configured.
- Mark-as-paid records a test dues payment and shows the fee split only when a percent is configured. No charge is made.
- Two members can sign up for a one-seat class; the second waits; when the first drops, the second is enrolled.
- An announcement appears for the member inside the portal and does not appear on the public listing.
- A rotation row assigns a parent.
- The Shelby County list order and pin colors are the same before and after the grant.
- A low category score on that group still follows the normal review rules.
- `groupPortal` off hides every portal link and page. Claims and reviews keep working. The stored roster remains.

## 9. Phase 4 — State law guides

Flag: `lawGuides`.

Each state can have one plain-language page, "Starting homeschool in {State}", linked from that state's map page. Content is researched and approved by David, one state at a time. **Claude does not draft the legal rules, even as a placeholder that could be mistaken for the law.**

### Data format

One file per state, `data/law/{state-code-lower}.json`, for example `data/law/tn.json`. Keep these out of `data/listings.json` so a listing rebuild is not mixed up with legal copy. The sample shape is the `lawGuide` object in `sample-data.json`.

| Field | What it is |
|---|---|
| `state` | Two-letter code. |
| `status` | `draft` or `approved`. The site renders `approved` only. |
| `title` | "Starting homeschool in Tennessee" (use the state's name). |
| `lastChecked` | ISO date David sets when he checks the sources. Null until then. |
| `disclaimer` | Fixed meaning: this is a plain-language summary, not legal advice, and families should read the official sources. |
| `who` | Who the page is for, in a short paragraph. |
| `steps` | Ordered list of `{ "heading", "body" }`. |
| `notice` | Paperwork or notice the state asks for. |
| `testing` | Testing or evaluation, when the state has it. |
| `umbrella` | Umbrella or cover schools, when relevant. For Mississippi, follow the existing note that the state does not require an umbrella school; do not invent a requirement. |
| `sources` | List of `{ "name", "url", "accessed" }`. Official pages only, cited, not paraphrased from memory into the file by Claude. |

### Page

Route: `/{state-code-lower}/homeschool-law/` (for example `tn/homeschool-law/`). Generate it from the JSON when status is `approved`. Unique title and meta description. Show the disclaimer at the top, then the sections, then the sources, then **"Last checked {date}"**. End with a link to the contact page ("Something look wrong?").

On the state map page, replace the current `lawBasics` placeholder box with the first paragraph and the last-checked date, plus "Read the full guide." If there is no approved file, leave a single line: "A plain-language guide isn't ready for {State} yet." Do not show draft text. Coming-soon states get that same one line when this module is on, and no line when it is off.

Tennessee and Mississippi are first in line because they are the pilot. Their current `lawBasics` strings stay in `data/listings.json` until an approved guide replaces the box. Do not rewrite those strings into something that sounds like legal advice.

### Acceptance

- A draft file produces no public page and no "read the guide" link.
- An approved sample whose body is clearly marked as sample layout, not law, renders the template: disclaimer, sections, sources, last checked.
- The Tennessee and Mississippi map pages do not show invented requirements.

## 10. Phase 5 — "Looking for" posts

Flag: `lookingFor`.

A family posts a need, for example "Spanish tutor near Collierville." Groups and other families reply. Same accounts, same public rules, same filter, same new-account hold, same flags, and the same queue. A low or urgent tone is not a hold reason. Children's names and home addresses are not allowed.

Fields: title, body, optional category (one of the 13 ids), state, county, optional city. No street address field.

Replies: a verified organization or another signed-in family may reply. Replies run through the filter. One level of replies is enough; no threads beyond that.

Where they show: a page `looking-for/` with state and county filters, and a short list on the matching county page ("Families here are looking for"). They do not become map pins.

`lookingForExpireDays` defaults to 90. After that the post leaves the public list. The author can renew it. Renewal runs the filter again.

### Acceptance

- A post with a child's name or a street address is held, not published.
- A clean post from an established account shows on the county page.
- A reply from a verified group shows under the post.
- The module flag hides the page, the county block, and the form.

## 11. Phase 6 — Local events calendar

Flag: `events`.

Park days, field trips, and co-op open houses, added by verified organizations and by signed-in families. Same filter, new-account hold, flags, and queue as reviews.

Fields: title, summary, start, end, state, county, city, a venue name that is a public place ("Shelby Farms visitor center", "the library"), and an optional `listingId`. There is no home-address field. A street address in the text is held. Linking a listing that already has a public organizational address is fine; the event borrows that listing's pin and does not copy a new address in.

Where they show:

- A list grouped by date, filterable by state and county. Month navigation can be "earlier / later". A full calendar grid is unnecessary for the test.
- On the county page, a short "Coming up" list.
- On the county map, a pin only when the event is tied to a listing that already has coordinates, or when it reuses coordinates already in the site's data. Use a different marker from the listing pins so a one-day park meetup is not mistaken for a permanent organization. No paid geocoding API, and no new map library for this.

Past events drop off the public list after `endsAt`. Keep the row.

This public calendar and the private group calendar (section 8) stay separate.

### Acceptance

- A family can add a park day that shows on the county list.
- An address in the summary holds the event.
- An event linked to a listing with a pin shows the distinct marker; an event with no pin stays in the list only.
- Flag off hides the list, the form, and those markers. Listing pins are unchanged.

## 12. Phase 7 — Trusted family badges

Flag: `badges`.

When `approvedReviewCount` reaches `trustedBadgeAfter` (default 3), the account is trusted. Published reviews by that account show a small "Trusted family" label. The count is the one phase 1 already updates. Do not weight their scores higher. A trusted review and a new family's review count the same in the averages.

Skip-the-wait stays on `newAccountHoldCount` (default 2). The badge can sit a step higher so it means "a few reviews in," not only "no longer brand new." David can set the two numbers independently.

Moderator path: on the admin account page, David can grant `moderator` to a trusted account. The control can also be used on an account that is not trusted yet, so he is not blocked during the test, but the page notes "Trusted families are the people this is for." No volunteer application form.

### Acceptance

- An account with 3 approved reviews shows the badge on its published reviews, and only when the flag is on.
- Averages do not change when the badge appears.
- An account with 2 approved reviews skips the wait (with the default settings) and does not yet show the badge.

## 13. Phase 8 — Saved favorites and alerts

Flag: `favorites`.

A signed-in family can save a listing from the card, the map preview, and the listing page. A "Saved" page lists them. Sign-in is required. Saving does not affect sort order.

Alerts they can opt into:

- Open spots changed on a saved listing (this needs the claims overlay; if claims is off, hide that checkbox).
- A new listing appeared in a chosen county.

Email: the footer signup is still a placeholder (`subscribe()` in `js/site.js` does not send). Any email-sending service needs David's approval, including one with a free tier, because many of them still ask for a card or start billing past a quota. Do not connect Buttondown, Mailchimp, or anything else as part of this module.

For the friends test, store the opt-in and show updates on the site: a short "Since your last visit" list on the Saved page. That list is the test. Real email can use the same stored opt-in later, after David picks a sender. The open question in `docs/map-pilot/claude-brief.md` (which email provider) is still open. Do not answer it here.

### Acceptance

- Save and unsave work on a card and on a listing page, and the Saved page matches.
- With no email provider, an open-spots change shows on "Since your last visit" and no email is sent.
- The module flag removes the save buttons and the Saved link.

## 14. What to keep

Do not remove or bypass these.

- The map, filters, zip and city search, clustering, and the phone layout from the map navigation brief.
- Draft ribbons, "We're still confirming this listing's details.", Featured as a hand-set tier, and "Last verified."
- The listing form and the footer email form, still disconnected, still with their honeypots.
- Listing ids, categories, and `data/listings.json` content. This work does not edit research copy.
- The rule that home addresses are not published. Organizational addresses already on a listing can stay.
- `data/site.json` `baseUrl`, `showDrafts`, and `allowSearchEngines`.

## 15. Test plan

Test on the GitHub Pages URL after the Render web service and the paid Postgres database are connected, and once locally with `python3 -m http.server` only for layout. Two browsers, or one browser and a private window, stand in for two families. Use Shelby County and these listings: Memphis Homeschool Enrichment Cooperative (MHEC), Spark Joy Homeschool Co-operative, and Bellevue Tutorial.

### Invite the friends

1. David signs in as the admin (the first admin is created in the backend setup he owns, not by a public "become admin" button).
2. He opens Admin settings, checks the invite code, and sends it himself to a few friends.
3. A friend opens https://dparkerson7.github.io/shareschooling-prototype/, creates an account, and enters the code. David marks that email verified on the admin page (the free web service cannot send a confirmation mail). The friend can then post.
4. A second family account and one organizer account are created the same way for the checks below.
5. A sign-up with the wrong code, or with the honeypot filled in, does not create an account.

### Reviews (flag on)

- Post a clean, kind review from an account that already has 2 approved reviews. It shows on the listing page, the county card, and the map preview. The comment can be left blank.
- Post a review with low scores and fair criticism from that same established account. It publishes. It is not in the queue because of the scores.
- From a brand-new account, post a clean review. It does not go public. It is in the queue with reason `new-account`. Approve it. The author can see it on the listing. A second new-account review still waits. After the second approval, a third clean review publishes immediately.
- Post a review that includes a phone number or a child's name. It is held with a filter reason. Edit out the problem in the queue and approve. The public text does not contain it.
- Flag a live review from another family account. Set `flagsToHide` to 1, flag once, and confirm the review disappears from the listing and shows in the queue. Set the number back to 3 and publish the review again.
- As a verified organizer, reply under a review. Sign out and confirm the reply is public. As an unverified account, confirm there is no reply box.
- In settings, turn the name check off, post a review that would have been held for a name, and confirm it is not held for that reason. Turn the check back on.
- Turn the `reviews` flag off. Cards, preview, and the listing page show no review UI, and the map still loads.

### Claimed listings (flag on)

- Claim MHEC by the path that matches its public email, or approve the claim in the queue if the test inbox is awkward.
- Set open spots and meeting days. The listing page and the card show them and an Updated date. Last verified is still the research date.
- Put a street address in the description. The old description stays public and the queue has the edit.
- Confirm the listing did not become Featured and did not move in the county list.

### Group portal (flag on, test payments only)

- Claim a group and verify it.
- As admin, grant the portal. Open it as the organizer without entering a card.
- Confirm the public county list order and the pins did not change, and the public page has no premium badge.
- Add a member by an invite the organizer can copy. Sign in as that member and see the group home. Confirm the roster is not on the public listing.
- Add a class with capacity 1 and a test fee. Sign up two members. The second is waitlisted. Drop the first. The second is enrolled and the fee is "due", with no charge.
- Record dues with "Mark as paid (test)". The screen shows a test record. If a dues percent is still null, it does not invent a platform fee. If David has set a percent in config for the test, the split shows and still says not collected.
- If, and only if, David has supplied Stripe test keys, pay a class fee with a test card and confirm the dashboard test view shows a test payment and no live payment. If keys are not supplied, this step is skipped and mark-as-paid is the pass.
- Send an announcement. It shows in the member's test outbox and not on the public listing. An announcement with a home address is held.
- Add the member to next month's Teach row on the rotation and confirm the member can see the schedule.
- Post a low-score review on this same group from an established family account. It follows the normal review rules and the group cannot turn reviews off.
- Turn `groupPortal` off. The portal links disappear. The claim's open-spots edit and the reviews remain.

### State law guides (flag on)

- A draft Tennessee file does not add a public guide link.
- An approved file whose text is a labeled layout sample, not legal advice, shows the disclaimer, the sections, the sources, and Last checked, and the state page links to it.
- A state with no file shows "isn't ready yet" and no invented rules.

### Looking for, events, badges, favorites

- Looking for: post "need a Spanish tutor near Collierville" from an established account. It shows on the Shelby page. A version that names a child is held. A verified group can reply.
- Events: add a park day with a public venue name. It shows on the county list. Tie one event to a listing that has a pin and confirm the marker is distinct. A home address in the summary is held.
- Badges: with `trustedBadgeAfter` at 3, an account with 3 approved reviews shows "Trusted family" on its reviews, and the averages did not change. Grant that account moderator and confirm they can open the queue and cannot open settings.
- Favorites: save a listing, see it on Saved, remove it. Change open spots on a saved claimed listing and see "Since your last visit." Confirm no email leaves the site.
- Turn each of these flags off in turn and confirm only that module disappears.

### Phone

At 360px, 390px, and 430px wide, the listing page with reviews, the queue, and the portal roster do not scroll sideways.

## 16. Open questions for David

1. **Invite.** One shared code is the default. Say if you want one link per friend.
2. **Rating words.** Is the starter list (welcoming, organized, communication, worth the time and cost) the one you want friends to see?
3. **Portal pricing.** Left unset on purpose. When you want a number: flat monthly fee, a small cut of dues, or both?
4. **Stripe.** Not required for the test. Mark-as-paid and the admin grant cover it. Say if you want a Stripe test-mode checkout added, and create the account yourself.
5. **Email sender** for alerts, confirmation mail, and real announcement mail. Still open from the map brief. The test uses the invite code, "Mark this email verified," and on-site messages until you pick one.
6. **Law guides.** Who gathers the Tennessee and Mississippi sources, and do you want the empty template built before that writing starts?
7. **Looking-for replies.** The brief allows both verified groups and other signed-in families to reply. Say if you want groups only.
