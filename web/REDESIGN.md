# Frontend redesign v3: "Editorial shelf"

Scope: `web/` only. Data contracts, routes, URL params, localStorage keys and the `library-files` Vite plugin stay as they are. This is a visual and structural redesign of the React app on top of Astryx.

## Direction

Reference set (Mobbin):

- Literal web library and book page: centered, airy, cover-first, serif display headings, quiet metadata, sort popover, list rows with small cover + title + author + status token. https://mobbin.com/screens/ad825620-0982-4c53-a104-0706a2bf7513 https://mobbin.com/screens/3ffcf3de-55bb-4e1f-9ac5-c8ff5d38604f https://mobbin.com/screens/34e65d3f-2c6c-4475-937a-849bde6439df
- Spotify audiobook page: ambient hero where the cover's colour bleeds into the header behind a very large title. https://mobbin.com/screens/2841bd13-3b86-451b-a3d3-1e922f80340f
- Apple Books and ElevenReader (iOS): horizontal shelves per category, chip row of categories on top, covers with a soft spine edge. https://mobbin.com/screens/b54b63f4-7c09-49de-8e22-1e74d6ef9588 https://mobbin.com/screens/1855b3cd-802f-4c27-bae7-5e9f22bd89b9
- Etsy shop and Skillshare browse: left rail of categories with counts, grid of covers to the right, sort and filters in one toolbar. https://mobbin.com/screens/aecebcc4-d2b0-4485-a5fc-2a623a15e17c https://mobbin.com/screens/d7fd93cd-32ec-425b-abb9-87bbe960c23b
- Bonsai and Causal command palette: "Recently viewed" when empty, grouped results, footer with key hints. https://mobbin.com/screens/a686898a-983d-4731-9946-fd0c2c2d00b4 https://mobbin.com/screens/f8956875-eefe-4d10-9499-1325950e40c2

Principles:

1. Covers are the UI. Everything else is quiet: one accent, neutral surfaces, small supporting text.
2. Editorial typography. Display and section headings use a serif; all body, labels, buttons stay Figtree.
3. One colour per page. The hero and the book page take an ambient tint from the cover; nothing else is tinted.
4. Mobile is a reading app: bottom tab bar, horizontal shelves, filters in a bottom sheet.

## Tokens and global styles (`web/src/styles.css`, `web/src/main.tsx`)

- Add `@fontsource/instrument-serif` (npm, bundled, no CDN). Import it in `main.tsx` next to Figtree.
- `--font-family-heading: "Instrument Serif", Georgia, "Times New Roman", serif;` on `[data-astryx-theme]`. Heading weight normal, `letter-spacing: -0.01em`. Body font stays Figtree. Buttons, labels, tokens, nav items stay Figtree (they use the body token).
- Keep `--shelf-cover-width: 150px` on desktop, `132px` under 640px.
- Covers: keep 2:3, `border-radius: var(--radius-element)`, existing shadow, plus `box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-border-default) 60%, transparent)` and a spine overlay `::after` with `linear-gradient(90deg, rgba(0,0,0,.16), transparent 7%)`. Hover lifts 2px as today. `prefers-reduced-motion` disables transforms.
- Ambient backdrop utility `.ambient`: an absolutely positioned, blurred (`filter: blur(48px)`), scaled copy of the cover image at `opacity: .35` light / `.25` dark, clipped by the parent, with a bottom gradient to `var(--color-background-body)`. Used by the Home hero and the Book page header only. The image is the same WebP already loaded for the cover, `aria-hidden`, `loading="lazy"` not needed because it is the priority image.
- Page width: `1200px` default, `880px` narrow, same paddings as today. Add `.page-frame-wide` at `1360px` for Browse.
- Dark mode unchanged (Astryx `mode`), ambient opacities differ as above.
- All custom CSS uses Astryx tokens for colour, spacing, radius, duration. No raw hex except inside `rgba` shadow values already present.

## Shell (`web/src/components/Shell.tsx`)

Desktop (>= 768px):

- `TopNav` stays. Heading: `NavIcon` with `BookOpen` + wordmark "Bookshelves" in the serif heading font (`className="wordmark"`).
- `startContent`: Home, Browse, Archive as `TopNavItem` (unchanged selection logic).
- Centre: the Search trigger becomes a full-width, input-looking button (`className="search-trigger"`): magnifier icon, placeholder text "Search titles, topics, descriptions", `Kbd mod+k` at the end. Max width 480px, grows to fill the middle. Built from `Button variant="secondary"` with custom class, or a read-only `TextInput` wrapped in a button if cleaner. Clicking opens the palette.
- `endContent`: theme toggle, GitHub. Same as today.

Mobile (< 768px):

- TopNav shows only the wordmark and the theme toggle.
- A fixed bottom tab bar (`.tabbar`, custom, Astryx tokens) with four items: Home, Browse, Search (opens palette), Archive. Icons from lucide (`House`, `LibraryBig`, `Search`, `Archive`), label under icon, selected item uses `--color-text-primary`, others `--color-text-secondary`. Height 56px plus `env(safe-area-inset-bottom)`. Page content gets bottom padding so nothing hides under it. Use `useMediaQuery("(max-width: 767px)")` from `lib/hooks`.
- Keyboard shortcuts `mod+k` and `/` unchanged.

## Search palette (`web/src/components/SearchPalette.tsx`)

- Keep `CommandPalette` from Astryx. Empty query shows a "Recently viewed" group from `recentIds` (max 6) and a "Browse" group with one item per category (navigates to `/browse?category=`). With a query, results group by category (group header = category name, max 8 per group, 24 total) using `searchBooks`.
- Each book item: 28px wide cover thumbnail (`BookCover size="sm"`), title, supporting line "topic leaf · formats". Enter opens `/book/:id`.
- Footer line: `Kbd` hints "↑↓ navigate · ↵ open · esc close" if CommandPalette does not render its own.

## Home (`web/src/pages/Home.tsx`)

Order top to bottom:

1. Hero "Today's pick" (`section.hero`): ambient backdrop from the cover. Grid: cover 240px (desktop) left, body right. Body: small uppercase supporting label "Today's pick", category / topic links as today, `Heading level={1} type="display-1"` title (serif), excerpt up to 3 lines (`Text type="large" color="secondary"`), buttons: primary `Download {format}`, secondary `Open`. On mobile: cover centred at 180px, text centred under it.
2. Library stats line under the hero: "173 books · 6 categories · 41 topics" as `Text type="supporting" hasTabularNumbers` (compute from `books` and `categories`).
3. Category chip row (`.chip-row`): one `Token` per category with `href={browsePath({category})}`, `endContent` = count, horizontally scrollable on mobile (`overflow-x: auto`, no scrollbar styling needed beyond `scrollbar-width: thin`), wraps on desktop.
4. "Recently viewed" shelf if any (unchanged source).
5. One shelf per category, same as today, with "View all" link and count. Shelf heading is serif via the global heading font.

Skeleton states mirror the new layout (hero skeleton + one shelf skeleton).

## Shelf and cards (`web/src/components/Shelf.tsx`, `BookCard.tsx`)

- Shelf: heading row left, "View all" right, then `Carousel hasSnap`. Add small ghost prev/next `IconButton`s on desktop if `Carousel` exposes controls; otherwise leave scrolling native. Check `npx astryx component Carousel` first.
- BookCard: cover, then title (`Text type="label" maxLines={2}`), then one supporting line. Below the supporting line add a quiet format row: `Token size="sm" color="gray"` per format, only when the book has more than one format. Keep `ClickableCard variant="transparent" padding={0}`.

## Browse (`web/src/pages/Browse.tsx`, `FilterRail.tsx`, `BookRow.tsx`)

Use `PageFrame width="wide"`.

Desktop layout: 260px rail + results.

- Rail (`FilterRail`) now holds three blocks, top to bottom:
  1. **Categories**: a list with "All books · N" first, then one row per category with count. Selected row uses `--color-background-selected` and primary text. Implement with `SideNav`/`SideNavItem` if its API fits a plain list with `href` and `isSelected`; otherwise `List`/`Item`. Check `npx astryx component SideNav` and `Item`.
  2. **Topics**: the existing `TreeList`, shown only when a category is selected. Heading "Topics" with a "Clear" link as today.
  3. **Format**: existing `CheckboxList`.
- Remove the `TabList` of categories from the main column; the rail replaces it.
- Main column header: `Heading level={1}` = category name or "All books", supporting count, and when a topic is active a second line with the topic path. Under it an **active filters** row of removable `Token`s (topic, each format, query) with a "Clear all" ghost button, shown only when at least one filter is active.
- Toolbar unchanged in function: filter `TextInput` (left), `Selector` sort + `SegmentedControl` grid/list (right).
- Grid: `Grid columns={{ minWidth: 160 }} gap={5} rowGap={7}`.
- List rows (`BookRow`): cover 44px, title (link), supporting "category / topic", then at the end `Token size="sm" color="gray"` per format and one small secondary `Download` `IconButton` for the primary format. Rows separated by `--color-border-subtle` 1px lines, 12px vertical padding, hover background `--color-background-hover`.
- Pagination unchanged.

Mobile layout:

- Horizontal category chip row at the top (same `.chip-row` as Home but tokens act as a single-select: selected token `color="blue"`, others default; "All" first).
- Toolbar: filter input full width, then a row with `Filters (n)` button (opens the existing `BottomSheet` containing the Topics + Format blocks only), sort selector, view toggle.
- Grid `minWidth: 132`.

## Book page (`web/src/pages/BookDetail.tsx`)

- Header (`section.book-hero`): ambient backdrop from the cover, full page width. Inside: breadcrumbs row (as today) at the top, then grid cover 260px left (desktop) and body right.
- Body: topic `Token`s row (one token per `topicParts` entry, each `href` to the browse path for that prefix), `Heading level={1} type="display-1"` title, supporting line "category · formats joined by ·".
- Action row: primary `Download {first format}`, secondary buttons for the other formats, ghost `Archive`/`Remove from archive`, ghost `Share`. Unchanged behaviour.
- Below the header, two columns on desktop (`.book-columns`): left `Description` (existing parser) with `Heading level={2}` "About this book"; right a `Card` with `MetadataList` (Category, Topic, Formats, File) and the download buttons repeated in a vertical stack so they are reachable after scrolling. On mobile the card comes after the description.
- Related: two shelves when they differ: "More in {topic leaf}" (same topic) and "More in {category}" (same category, other topics). Build both from `relatedBooks` logic split into two helpers in `lib/data.ts` (`sameTopicBooks`, `sameCategoryBooks`). Hide an empty shelf.
- Mobile: cover centred at 200px, title and tokens centred, action row wraps.

## Archive (`web/src/pages/Archive.tsx`)

- Header: `Heading level={1}` "Archive" with count, supporting line as today.
- Rows reuse `BookRow`, plus a trailing ghost `IconButton` `ArchiveRestore` labelled "Remove from archive" that calls `toggleArchived` (add an optional `trailing` slot prop to `BookRow`).
- Empty state unchanged in copy.

## Not found (`web/src/pages/NotFound.tsx`)

Unchanged except headings now serif through the token.

## Accessibility and quality bar

- Every interactive element has a visible focus ring (Astryx default); do not remove outlines.
- The ambient image is `aria-hidden` and `alt=""`.
- Colour contrast of text over the ambient area must meet AA; keep text on `--color-background-body` surfaces, and the ambient opacity low.
- `prefers-reduced-motion`: no transforms or transitions on covers.
- No layout shift: covers reserve 2:3 space, the hero reserves its height with the skeleton.
- Lighthouse-style basics: lazy covers off-screen, priority on hero and book page covers.

## Done means

- `cd web && npm run build` passes with zero TypeScript errors.
- `python scripts/cli.py smoke --base-dir .` passes from the repo root.
- Light and dark mode checked on `/`, `/browse`, `/browse?category=…&topic=…`, `/book/:id`, `/archive`, `/nope` at 375px and 1280px widths.
- No git commit or push. The user commits.

---

# Home v2

Replaces the "Home" section above. Problems with v1: one tall hero box with a small cover floating in empty space, a stats line and chip row that feel bolted on, then five identical shelves with no rhythm. Nothing says "your library", nothing invites a next action.

Extra references (Mobbin): Audible home with genre tiles and a numbered "Top" list https://mobbin.com/screens/750525df-f134-4449-b96a-490d3b510e11 https://mobbin.com/screens/2cf2f893-2d65-4da8-94cc-9506a89930da ; Julienne discover page with topic chips over shelves https://mobbin.com/screens/c5c37f34-b6fc-47dd-82ea-e58223bcd341 ; Babbel greeting header https://mobbin.com/screens/8f0fb298-840c-4448-86b6-f362af935599 ; Matter "Top picks" cards https://mobbin.com/screens/d2a723f2-d379-4900-8131-b2a679760e8b

Order top to bottom (desktop 1200px frame):

1. **Greeting header** (`.home-greeting`). `Heading level={1} type="display-2"` in serif: "Good morning." / "Good afternoon." / "Good evening." by local hour (5–11 / 12–17 / else). Under it `Text type="large" color="secondary"`: "{N} books on {M} shelves. Pick one." where N = merged books, M = categories. No stats line anywhere else.

2. **Hero row** (`.home-hero`): two columns, 7fr / 5fr, gap `--spacing-6`, equal height.
   - Left, **Today's pick card** (`.pick-card ambient-host`, radius `--radius-container`, padding `--spacing-6`, `AmbientBackdrop`): small uppercase supporting label "Today's pick"; grid cover 180px (`BookCover size="lg" priority`) + body; body = category / topic links, `Heading level={2} type="display-3"` title, excerpt 2 lines (`Text type="body" color="secondary" maxLines={2}`), buttons primary `Download {fmt}` + secondary `Open`. Keep the card around 300px tall on desktop; it must not grow with the title.
   - Right, **Jump back in card** (`.recent-card`, `Card` from Astryx with padding `--spacing-5`): heading row `Heading level={2}` "Jump back in" + `Link` "Archive" to `/archive`. Body: a numbered list of the last 4 `recentIds` (Audible style): index numeral in serif `Text type="large"` 24px wide, 40px cover (`BookCover size="sm"`), title (link, 1 line) and supporting "category · topic leaf". Rows 56px tall, separated by `--color-border`. If there are no recents, heading becomes "Start here" and the list shows 4 books, one from each of the first four categories (deterministic: the first book of each category). Mobile: this card goes under the pick card.

3. **Shelves tiles** (`.category-tiles`): `Heading level={2}` "Your shelves". Grid `Grid columns={{ minWidth: 220 }} gap={4}`. One `ClickableCard` per category (`href` to browse) laid out as: left column = category name (`Heading level={3}` serif, 2 lines max) + supporting "{count} books · {topicCount} topics"; right = a fan of 3 covers from that category (`.cover-fan`: three `BookCover size="sm"` at 44px width, absolutely stacked with 14px offsets and 4°/0°/-4° rotation, the middle on top). Card height 112px, padding `--spacing-4`, background `--color-background-surface`, hover lifts 1px. Fan covers are `aria-hidden`. Covers chosen: first three books of the category that have a cover.

4. **Topics strip** (`.topic-strip`): `Heading level={3}` "Browse by topic" then a `.chip-row` of `Token size="md"` for the 12 most populated topic leaves across the library (leaf name, count as endContent, `href` to `browsePath({ category, topic })`). Sort by count desc then name. Add a trailing ghost `Button` "All topics" → `/browse`.

5. **Category shelves**: one `Shelf` per category as today, max 12 books, heading row = category name (serif), count, "View all". Under the heading add one supporting line listing up to 4 topic names of that shelf joined by " · " (`Text type="supporting" maxLines={1}`), so each shelf reads differently. Keep the Carousel.

6. **Footer action** (`.home-footer`): centered `Text type="supporting"` "Don't know what to read?" + secondary `Button` "Surprise me" with `Shuffle` icon that navigates to a random book (`useNavigate`, `Math.random` over `books`). Padding top `--spacing-8`.

Remove from v1: the old full-width hero, the stats line, the category chip row.

Mobile (< 640px): greeting display-3; pick card stacks (cover 140px centered, text centered, buttons wrap); recent card below; tiles 1 column with the fan on the right; topic strip scrolls horizontally; shelves as today; footer button full width above the tab bar.

Skeleton: greeting text skeleton, pick card skeleton, recent card with 4 row skeletons, 4 tile skeletons, one shelf skeleton.

Helpers to add in `web/src/lib/data.ts`: `greetingForHour(hour)`, `topTopics(books, limit)` returning `{ category, topic, leaf, count }[]`, `sampleCovers(books, category, n)`, `firstBookPerCategory(books, categories, n)`.

Done means: same as the main section (build, smoke, 375px/1280px light+dark), plus a screenshot of `/home` with and without `recentIds` in localStorage.

---

# Nav v2

Replaces the "Shell" section above. Problems with v1: the bar spans the full viewport while the page frame is 1200px, so the logo and links do not line up with the content; the three links are grey pills; the search trigger is a 480px input-looking pill that dominates the bar; nothing separates the bar from the page.

References (Mobbin): Linear https://mobbin.com/sites/sections/192414ab-334b-4a7f-a278-1d4cf5bdc095 , Resend https://mobbin.com/sites/sections/3a3c66b0-d727-4fe4-b368-db103afd5b6b , Runway https://mobbin.com/sites/sections/754769a3-efe7-48cb-98bb-547e66bfdfee : thin bar, plain text links, controls as small icon buttons on the right, one hairline below.

Desktop (>= 768px), `header.nav` (custom, replaces Astryx TopNav; keep AppShell if it still helps, otherwise render `header` + `main` yourself):

- Sticky at top, `z-index` above content, height 56px. Background `color-mix(in srgb, var(--color-background-body) 85%, transparent)` with `backdrop-filter: blur(12px)`. Bottom hairline `1px solid var(--color-border)`.
- Inner container `.nav-inner`: same width and horizontal padding as `.page-frame` (1200px, `--spacing-5`), so the wordmark's left edge and the GitHub button's right edge align with page content. On `/browse` the page frame is 1360px; the nav stays 1200px, that is fine.
- Layout: flex, `align-items: center`, three groups: brand, links, controls. Gap between brand and links `--spacing-8`; controls pushed right with `margin-inline-start: auto`.
- **Brand** (`.brand`): `BookOpen` icon at 18px in `--color-text-primary` and "Bookshelves" in the serif at `--font-size-xl`, gap `--spacing-2`, link to `/home`, no box around the icon, no NavIcon.
- **Links** (`.nav-links`): Home, Browse, Archive as plain text links, `--font-size-sm`, `--font-weight-medium`, height 56px (full bar) so the active indicator can sit on the hairline. Colour: `--color-text-secondary`, hover `--color-text-primary`, active `--color-text-primary` plus a 2px bar at the bottom of the link in `--color-text-primary` (`::after`, positioned at `bottom: -1px` so it overlaps the hairline). Padding `0 var(--spacing-1)`, gap between links `--spacing-5`. Use `RouterLink` or react-router `NavLink`; no pills, no background.
- **Controls** (`.nav-controls`): all items 32px tall, gap `--spacing-1`.
  1. Search trigger: `Button variant="secondary" size="sm"` (check `npx astryx component Button` for the size prop) with `Search` icon, text "Search" and `Kbd mod+k` inside, radius `--radius-element`, width auto (about 150px), not full-width. Keyboard behaviour unchanged.
  2. A vertical divider: `Divider orientation="vertical"` (check API) 20px tall, margin `0 var(--spacing-2)`.
  3. Theme toggle `IconButton variant="ghost" size="sm"`.
  4. GitHub `IconButton`/`Button isIconOnly variant="ghost" size="sm"`.
- Remove `centerContent` and the 480px `.search-trigger`. Remove `.wordmark` overrides on TopNavHeading if TopNav is no longer used.

Mobile (< 768px):

- Same `header.nav`, height 52px, inner padding `--spacing-4`: brand left, right `IconButton` Search (opens the palette) and the theme toggle. No links.
- Tab bar unchanged in structure; give it the same translucent background and blur as the header, hairline on top.

Focus and a11y: all links and buttons keep the Astryx focus ring; `aria-current="page"` on the active link; the header is a `<header>` containing `<nav aria-label="Main">`.

Done means: build and smoke pass; screenshots at 1280 and 375, light and dark, on `/home` and `/browse`; the wordmark's left edge lines up with the "Good afternoon." heading on `/home` at 1280 (measure both x positions and report them).

---

# Nav v3

Replaces Nav v2. What is wrong with v2, seen at 2x: with only two links the bar is lopsided (brand + Home + Browse on the left, then a 900px void); the active underline is 2px at the very bottom edge, wider than the word and 20px below it, so it reads as a stray line; the Search trigger is a filled grey block far heavier than the ghost icons next to it; the Kbd inside it adds clutter.

Reference: Literal web header https://mobbin.com/screens/3ffcf3de-55bb-4e1f-9ac5-c8ff5d38604f : brand left, a real search field in the middle, text links and icons right.

Desktop (>= 768px), `header.nav` stays sticky with blur and the bottom hairline, height 56px, `.nav-inner` 1200px aligned with the page frame.

Three zones, `display: grid; grid-template-columns: 1fr minmax(320px, 520px) 1fr; align-items: center; gap: var(--spacing-6)`:

1. **Brand** (left, `justify-self: start`): `BookOpen` 20px, stroke 2, colour primary; "Bookshelves" serif `--font-size-xl`; gap `--spacing-2`. Link to `/home`.
2. **Search field** (center): a button that looks like an input, `.nav-search`: height 36px, width 100%, `border: 1px solid var(--color-border)`, `background: var(--color-background-surface)`, `border-radius: var(--radius-full)` (pill), padding `0 var(--spacing-3)`, `display: flex; align-items: center; gap: var(--spacing-2)`. Left: `Search` icon 16px in `--color-text-secondary`. Middle: placeholder text "Search books, topics…" in `--color-text-secondary`, `--font-size-sm`, `flex: 1`, left-aligned, ellipsis. Right: `Kbd keys="mod+k"` at reduced opacity (`.7`). Hover: `border-color: var(--color-border-emphasized)`. Focus-visible: Astryx focus ring. Click opens the palette. Build it as a plain `<button type="button">` with the class, not Astryx Button, so it does not pick up button styling.
3. **Right cluster** (`justify-self: end`, `display: flex; align-items: center; gap: var(--spacing-1)`):
   - Home and Browse as text links `.nav-link`: `--font-size-sm`, `--font-weight-medium`, height 32px, padding `0 var(--spacing-3)`, `border-radius: var(--radius-element)`, colour `--color-text-secondary`; hover `background: var(--color-overlay-hover)` and colour primary; active (`aria-current="page"`) colour `--color-text-primary` and `background: var(--color-background-muted)`. No underline, no `::after`.
   - `Divider orientation="vertical"` 20px, `margin: 0 var(--spacing-2)`.
   - Theme toggle `IconButton variant="ghost"` 32px and GitHub ghost icon button 32px, same as now.

Between 768px and 1000px: the search column shrinks to `minmax(220px, 1fr)` and the placeholder text shortens to "Search" (use a CSS `@media` to hide the long text and show a short one; two spans).

Mobile (< 768px): keep v2 behaviour (brand left; right: Search `IconButton` + theme toggle), height 52px. Tab bar unchanged.

Palette: unchanged.

Done means: build and smoke pass; 2x screenshots of the bar at 1280 and 900, light and dark, on `/home` and `/browse`; the search field is visually centred in the bar (report its left and right margins to the brand and to the right cluster at 1280).

---

# Nav v4

Replaces Nav v3. The user rejected v3 (big bordered search pill, grey active pill, generic SaaS look). v4 copies the structure of the Literal header: zones separated by full-height hairlines, a borderless search zone, text-only links. No pills, no filled backgrounds anywhere in the bar.

Reference: https://mobbin.com/screens/3ffcf3de-55bb-4e1f-9ac5-c8ff5d38604f

Desktop (>= 768px): `header.nav` sticky, height 56px, background `color-mix(in srgb, var(--color-background-surface) 92%, transparent)` with 12px blur, bottom hairline `1px solid var(--color-border)`. `.nav-inner` 1200px, aligned with the page frame, `display: flex; align-items: stretch; height: 100%`.

Zones, left to right, each separated by a vertical hairline `1px` of `var(--color-border)` spanning the full 56px (use `border-inline-start` on the zone, not a Divider component):

1. **Brand** `.nav-brand`: `BookOpen` 20px stroke 2 + "Bookshelves" serif `--font-size-xl`, gap `--spacing-2`, `padding-inline-end: var(--spacing-5)`, link to `/home`, `display: inline-flex; align-items: center`. No hairline on its left.
2. **Search** `.nav-search`: `flex: 1 1 auto; min-width: 0`, a plain `<button>` with no border, no background, no radius, `padding-inline: var(--spacing-5)`, `display: flex; align-items: center; gap: var(--spacing-3)`, text-align start. Content: `Search` icon 16px `--color-text-secondary`, span "Search for books, topics, descriptions…" `--font-size-sm` `--color-text-secondary` ellipsis flex 1, and at the far right `Kbd keys="mod+k"` at `opacity: .6`. Hover: text and icon turn `--color-text-primary`. Focus-visible: focus ring with negative offset (`outline-offset: -3px`) so it stays inside the bar. Clicking opens the palette.
3. **Links** `.nav-links`: `display: flex; align-items: center; gap: var(--spacing-6); padding-inline: var(--spacing-6)`. Home, Browse as `.nav-link`: `--font-size-sm`, `--font-weight-medium`, colour `--color-text-secondary`, no padding, no background, no underline; hover and `aria-current="page"` colour `--color-text-primary`. That is the whole active state, like Literal.
4. **Controls** `.nav-controls`: `display: flex; align-items: center; gap: var(--spacing-1); padding-inline-start: var(--spacing-4)`: theme toggle and GitHub ghost `IconButton`s 32px.

Between 768px and 1000px: the search text shortens to "Search" (two spans with a media query) and the Kbd is hidden.

Mobile (< 768px): height 52px, flex `space-between`: brand (no hairline) left; right cluster: Search `IconButton` + theme toggle, both ghost. No hairlines on mobile. Tab bar unchanged.

Done means: build and smoke pass; 2x screenshots of the bar at 1280 and 900, light and dark, on `/home` and `/browse`; confirm no element in the bar has a filled background other than the bar itself.

---

# Nav v5: sidebar

Replaces every top-bar version (v2–v4). The user rejected all top-bar variants. v5 switches the desktop shell to a left sidebar, like Spotify, Matter and MasterClass (Mobbin refs: https://mobbin.com/screens/fd3a6dc1-98fb-422a-8d9f-2a0c07635516 https://mobbin.com/screens/d2a723f2-d379-4900-8131-b2a679760e8b https://mobbin.com/screens/e8211855-5f5a-49dc-a6e8-254554ea8029 ). UX gains: search is always in the same place, the category shelves are one click away from every page, recently viewed books are reachable from anywhere, and the content column has no bar competing with page headings.

## Desktop (>= 1024px)

Use Astryx `AppShell` with `height="fill"`, `variant="section"`, `mobileNav={false}`, no `topNav`, and `sideNav={<SideNav …>}` (check `npx astryx component SideNav`, `SideNavHeading`, `SideNavItem`, `SideNavSection`, `SideNavCollapseButton`).

SideNav, width 260px, `collapsible` on (built-in toggle in the footer icon bar), not resizable:

1. `header`: `SideNavHeading` with the `BookOpen` icon and "Bookshelves" (serif through a `wordmark` class on the heading text), link to `/home`.
2. `topContent`: the search trigger `button.side-search`, full width, height 36px, `border: 1px solid var(--color-border)`, `background: var(--color-background-surface)`, `border-radius: var(--radius-element)`, padding `0 var(--spacing-3)`, flex with gap `--spacing-2`: `Search` icon 16px secondary, text "Search" `--font-size-sm` secondary flex 1 left-aligned, `Kbd keys="mod+k"` at the end. Hover border `--color-border-emphasized`. Opens the palette. Margin `var(--spacing-2) var(--spacing-3) var(--spacing-3)`.
3. `children`:
   - `SideNavSection` without a title: `SideNavItem` Home (`House`, `/home`), Browse (`LibraryBig`, `/browse`). `isSelected` from the current section (home = `/home`; browse = `/browse` and `/book/*`).
   - `SideNavSection` titled "Shelves": one `SideNavItem` per category from `useLibrary().categories`, label = category name (ellipsis, 1 line), `href = browsePath({ category })`, and the count at the end (use the item's end/badge slot if it has one, else a `Text type="supporting" hasTabularNumbers` child; check the API). `isSelected` when the path is `/browse` and the `category` query param equals that name. Icon: none for these (keep them lighter than the two primary items) unless SideNavItem requires one, in which case use `Folder`.
   - `SideNavSection` titled "Recently viewed", only when `recentIds` is non-empty: up to 3 `SideNavItem`s, label = book title (ellipsis), `href = bookPath(id)`, `isSelected` when on that book's page.
4. `footerIcons`: theme toggle `IconButton variant="ghost"` and the GitHub ghost icon button; the built-in collapse button sits with them.

Collapsed state: the two primary items show as icons; the Shelves and Recently viewed items need an icon to be usable collapsed, so give Shelves items the `Folder` icon and Recently viewed items `BookOpen` only if collapsed mode otherwise hides them (check how SideNavItem behaves without an icon when collapsed and decide; report what you did).

Content column: `AppShell` renders `<main>`; pages keep their `PageFrame` widths (1200 / 1360 wide for Browse) centred in the content column. `contentPadding={0}`. The main column scrolls, the sidebar stays fixed. `window.scrollTo` calls in pages still need to work: if `height="fill"` makes `main` the scroll container, replace those calls with scrolling the main element (export a `scrollToTop()` helper from `lib/hooks.ts` that finds `main` and scrolls it, and use it in Browse.tsx and BookDetail.tsx; coordinate: shell adds the helper, browse and home switch their calls).

Browse page on desktop: the `FilterRail` drops its Categories block (the sidebar owns categories now) and shows only Topics and Format. The Browse header keeps the H1 (category or "All books") and the active-filter tokens. The rail should still show "All books" context: when no category is selected the Topics block says "Pick a shelf in the sidebar to filter by topic." (current copy adapted).

## Mobile and tablet (< 1024px)

Keep the current mobile shell: slim top bar 52px with brand left, Search `IconButton` and theme toggle right (no hairline zones), and the bottom tab bar Home / Browse / Search. Browse keeps its category chip row and Filters sheet. The breakpoint for "mobile" moves from 768px to 1024px everywhere in Shell.tsx so there is never a top bar and a sidebar at the same time.

## Done means

- build and smoke pass.
- Screenshots at 1280 (sidebar expanded and collapsed) and 375, light and dark, on `/home`, `/browse?category=Software%20Engineering`, `/book/3b4df7a575ec`.
- Keyboard: Tab order goes brand → search → Home → Browse → shelves → recent → footer icons; `mod+k` still opens the palette; the selected item has `aria-current="page"`.
- Scrolling a long page (Home) and then navigating to a book lands at the top of the book page.

---

# Browse v2: topic chips instead of the rail

Replaces the desktop Browse rail. Problems: with the sidebar in place, the Topics tree is a second vertical nav next to the first; the indented TreeList with chevrons and far-right counts is slow to scan; the rail costs 300px that the cover grid needs; the active token repeats the full "Parent/Child" path.

References: drill-down chip rows in Julienne https://mobbin.com/screens/c5c37f34-b6fc-47dd-82ea-e58223bcd341 , ElevenReader https://mobbin.com/screens/1855b3cd-802f-4c27-bae7-5e9f22bd89b9 , Apple News https://mobbin.com/screens/87220b75-a523-4cff-a71c-21312f576d8d .

## Layout (desktop >= 1024px, inside the sidebar shell)

No rail. One column, `PageFrame width="wide"`.

1. **Header**: `Heading level={1}` = category name or "All books", supporting count. No topic subtitle line and no active-filter token row (the chips and the toolbar show the state).
2. **Topic chips, level 1** (`.topic-chips`), only when a category is selected: a wrapping row of `Token size="md"` (or Astryx `ToggleButton` if it is a better fit for a single-select group; check `npx astryx component ToggleButton` and `Token`): first chip "All" (count = category total), then one chip per top-level `TopicNode` of the category with its count as `endContent`. Selected chip: `color="blue"`; others default. Clicking sets `topic` to that node path (or clears it for "All"). The row is a `role="group"` with `aria-label="Topics"` and the selected chip has `aria-pressed="true"`.
3. **Topic chips, level 2**, only when the selected level-1 node has children: a second row under the first, indented by nothing, visually lighter (`size="sm"`): first chip "All {parent leaf}" (count = parent count) then one per child with count. Selected child chip `color="blue"`. Clicking sets `topic` to the child path; "All {parent}" sets `topic` back to the parent path. Deeper levels repeat the same pattern (one row per level).
4. **Toolbar**: filter `TextInput` left; right: a `Format` single-select built from `SegmentedControl` with items "All", "PDF", "EPUB" (only formats present in the library; DOCX appears if present), the `Selector` sort, and the grid/list `SegmentedControl`. Format becomes single-select: the `format` query param holds one value or none (the parser already accepts a list; writing one value keeps old URLs working). When any of topic, format or query is active, add a ghost `Button` "Reset" at the end of the toolbar that clears `q`, `topic` and `format`.
5. **Grid**: `Grid columns={{ minWidth: 160 }}` now spans the full content width (expect 5–6 columns at 1280 with the sidebar expanded).
6. Pagination unchanged.

With no category selected ("All books"): no topic rows at all; header, toolbar and grid only.

## Mobile (< 1024px)

Keep the category chip row at the top (it replaces the sidebar there). Below it, the same topic chip rows as desktop, each horizontally scrollable (`.chip-row`), and the toolbar with the filter input, the Format segmented control, sort and view. The Filters `BottomSheet` and the `Filters (n)` button are removed; nothing is left to put in them.

## Cleanup

- Delete `FilterRail.tsx` and the `.browse-layout`, `.browse-rail`, `.sheet-body` and `.active-filters` CSS blocks. Add `.topic-chips` (wrap, gap `--spacing-2`) and `.topic-chips-sub` (same, `margin-top: var(--spacing-2)`).
- `Browse.tsx` keeps the URL contract: `category`, `topic`, `format`, `q`, `sort`, `page` all still work and old links with `format=pdf,epub` still load (treat a list as "first value").

## Done means

- build and smoke pass.
- Screenshots at 1280 (sidebar expanded) and 375 of `/browse`, `/browse?category=Computer%20Science%20Fundamentals`, `/browse?category=Computer%20Science%20Fundamentals&topic=Programming%20Languages`, `/browse?category=Computer%20Science%20Fundamentals&topic=Programming%20Languages/Go`, and one with `format=epub`.
- Clicking through: category → topic → sub-topic → "All Programming Languages" → "All" updates the URL and the count each time; Reset clears q/topic/format and keeps category and sort.

---

# Browse v3: topic shelves (chosen by the user)

Replaces Browse v2 (chips) and the v1 rail. Model: opening a shelf shows its books as horizontal rows per topic, like Apple Books and Spotify browse; a leaf topic shows a flat grid. No topic filter UI anywhere.

References: https://mobbin.com/screens/fd3a6dc1-98fb-422a-8d9f-2a0c07635516 , https://mobbin.com/screens/b54b63f4-7c09-49de-8e22-1e74d6ef9588

## Modes (same route `/browse`, same query params)

Let `node` be the `TopicNode` selected by `topic` inside the selected category (or the category root when `topic` is empty).

1. **Catalog** (`/browse`, no category): H1 "All books" + count; toolbar; flat grid or list of every book; pagination. Unchanged from today except the chips are gone.
2. **Shelf mode** (category selected and `node` has children, and `q` is empty): 
   - Header: Astryx `Breadcrumbs` (Library → category → each topic ancestor → current, current `isCurrent`) above `Heading level={1}` = category name (root) or topic leaf, with supporting count. One line under the H1 listing the child topic names joined by " · " (`Text type="supporting" maxLines={1}`).
   - Toolbar: filter `TextInput` (typing switches to grid mode for the same node) and the Format single-select `SegmentedControl` ("All", then formats present). No sort, no view toggle, no Reset in this mode.
   - Body: one `Shelf` per child node, ordered by count desc then name. Shelf title = child name, `count` = child count, `href` = `browsePath({ category, topic: child.path })`, `linkLabel` "See all", `description` = that child's own child names joined by " · " when it has any. Books in the shelf = all books under the child path (`topicMatches`), first 12, sorted by title. Books that sit directly on `node` (not in any child) go into a last shelf titled "Other in {node name}" only when there are any.
   - Shelf cards use `BookCard showCategory={false}` so the supporting line shows the topic leaf.
3. **Grid mode** (category selected and `node` is a leaf, or `q` is non-empty): same header as shelf mode (breadcrumbs, H1, count), toolbar with filter `TextInput`, Format segmented, sort `Selector`, grid/list `SegmentedControl`, and a ghost "Reset" button when `q` or `format` is set (clears only those). Body = the paginated grid/list of books under `node`, as today.

Format filter applies in every mode. `format` in the URL stays a single value; a legacy list is read as its first value.

## Mobile (< 1024px)

Category chip row at the top as today (it is the shelf picker there). Then the same header, toolbar and body as desktop. Shelves scroll horizontally with the existing `Carousel`.

## Cleanup

- Remove the topic chip rows and their CSS (`.topic-chips*`, `.topic-chip-count`). `FilterRail.tsx` stays deleted. No bottom sheet.
- Keep `Shelf.tsx` as is; it already has `description`, `count`, `href`, `linkLabel`.
- Add to `lib/data.ts`: `findTopicNode(category: CategorySummary, path: string): TopicNode | null` and `booksDirectlyUnder(books, topicPath)`.

## Done means

- build and smoke pass.
- Screenshots at 1280 (sidebar expanded) and 375 of: `/browse`, `/browse?category=Computer%20Science%20Fundamentals` (shelves: Programming Languages, Systems and OS, Data Structures…, with "See all"), `/browse?category=Computer%20Science%20Fundamentals&topic=Programming%20Languages` (shelves per language), `/browse?category=Computer%20Science%20Fundamentals&topic=Programming%20Languages/Go` (grid of 9), and the last one with `q=web` (grid, Reset visible).
- Click-through: sidebar shelf → topic "See all" → sub-topic "See all" → breadcrumb back to the category; URL and counts update at each step.

---

# Browse v4: topics live in the sidebar (chosen by the user)

Replaces Browse v3 (topic shelves). Model: the sidebar "Shelves" section is a tree: each shelf expands into its topics, and topics with sub-topics expand again. The Browse page has no topic UI at all: header, toolbar, grid or list, pagination. One tree, one place. Reference: MasterClass https://mobbin.com/screens/e8211855-5f5a-49dc-a6e8-254554ea8029 and Notion/Spotify-style nested sidebars.

## Sidebar (Shell.tsx, desktop >= 1024px)

Check `npx astryx component SideNavItem` for nested children / collapsible items first. If `SideNavItem` supports child items with a disclosure toggle, use it; otherwise build the nesting with `TreeList` inside the section (check `npx astryx component TreeList`) and report which you used.

- "Shelves" section: one row per category. Row label = category name, `endContent` = count. Clicking the label navigates to `browsePath({ category })`. The row has a disclosure chevron that toggles its children without navigating.
- Children of a category: its top-level `TopicNode`s, label = topic name, count at the end, `href = browsePath({ category, topic: node.path })`. A topic that has children gets its own chevron and nests one more level (sub-topics, same shape). Depth is whatever the data has (currently 2).
- Expansion state: the category of the current URL and the ancestors of the current `topic` are expanded automatically on navigation; the user can toggle any row manually, and manual toggles persist for the session (React state in Shell, not localStorage). Everything else starts collapsed.
- Selection: exactly one row has `isSelected` / `aria-current="page"`: the deepest row matching the URL (topic row on a topic page, category row on a category page, nothing when on `/browse` without category).
- Indentation: 16px per level, counts right-aligned in `--color-text-secondary` tabular numbers, rows 32px tall, labels ellipsis on one line. Chevron 16px, rotates 90° when expanded, `aria-expanded` on the toggle.
- Collapsed rail mode: category rows show the `Folder` icon with a flyout of their topics if the component supports flyouts; otherwise just the icon linking to the category.
- "Recently viewed" section unchanged below.

## Browse page (Browse.tsx)

- Header: `Breadcrumbs` (Library → category → topic ancestors → current, only when a category is selected), `Heading level={1}` = topic leaf, or category name, or "All books"; supporting count.
- Toolbar: filter `TextInput` (left); right: Format single-select `SegmentedControl` ("All" + formats present), sort `Selector`, grid/list `SegmentedControl`, and a ghost "Reset" button when `q` or `format` is set (clears only those).
- Body: paginated grid (`Grid columns={{ minWidth: 160 }}`) or list of the books under the current node, as in v3 grid mode. No shelves, no chips, no topic rows, no child-topic line under the H1.
- URL contract unchanged: `category`, `topic`, `format`, `q`, `sort`, `page`.

## Mobile (< 1024px)

No sidebar there, so: keep the category chip row at the top, and add a "Topics" button (`Button variant="secondary"` with `ListTree` icon, label "Topics" or "Topics · {leaf}" when one is selected) next to the filter input, shown only when a category is selected. It opens a `BottomSheet` with a `TreeList` of that category's topics (same data as the sidebar tree, selected row highlighted, counts at the end); tapping a row navigates and closes the sheet; a "All topics in {category}" row at the top clears `topic`. Format stays in the toolbar.

## Cleanup

- Remove the v3 shelf-mode code from Browse.tsx (`findTopicNode` / `booksDirectlyUnder` may stay in data.ts if the sidebar or the sheet uses them; delete them if unused).
- Remove any Browse CSS no longer referenced.

## Done means

- build and smoke pass.
- Screenshots at 1280 (sidebar expanded, with Computer Science Fundamentals expanded and Programming Languages expanded, Go selected) and 375 (chip row, Topics sheet open) of: `/browse`, `/browse?category=Computer%20Science%20Fundamentals`, `…&topic=Programming%20Languages`, `…&topic=Programming%20Languages/Go`.
- Click-through at 1280: sidebar chevron on a shelf expands without navigating; clicking the shelf label navigates and expands; clicking "Programming Languages" navigates and expands its children; clicking "Go" selects it; breadcrumb "Computer Science Fundamentals" goes back and keeps the tree expanded. Keyboard: chevrons and rows are reachable with Tab, Enter/Space toggles or activates, `aria-expanded` and `aria-current` are correct.

---

# Browse toolbar v2

Replaces the toolbar in Browse v4. Problems: three different control shapes (pill input, segmented group, select, icon pair) with different heights and radii, no labels, and a void across the middle.

Reference: filter bars in Lovable https://mobbin.com/screens/0b9fce46-e8b8-48ac-a6b1-b983ebbb5e15 and Base44 https://mobbin.com/screens/6341b4d5-ae9f-46fe-9a2d-51820d818074 : one row of same-height controls, dropdowns with descriptive option labels, view switch at the far right.

Desktop (>= 1024px), `.browse-toolbar`: `display: flex; align-items: center; gap: var(--spacing-2)`; every control 36px tall with `--radius-element` (not pill). Check `npx astryx component TextInput`, `Selector`, `SegmentedControl`, `Button` for size props and pick the size that renders 36px; report it.

Left group, in this order:
1. Search `TextInput`, width 280px, leading `Search` icon (use the component's icon slot if it has one; otherwise an `InputGroup`, check `npx astryx component InputGroup`), placeholder "Filter titles…", `hasClear`, label hidden.
2. Format `Selector`, width 150px, options "All formats", "PDF only", "EPUB only" (only formats present; DOCX if present). Value from `format`.
3. Sort `Selector`, width 170px, options "Title A–Z", "Title Z–A", "By category". Disabled with the existing message while a query is active.
4. When `q` or `format` is non-default: ghost `Button` "Reset" with the `X` icon, same height.

Right group (`margin-inline-start: auto`): the grid/list `SegmentedControl` with icon-only items, same 36px height.

The right-hand result count stays in the H1 line, not in the toolbar.

Mobile (< 1024px): row 1 = search input full width; row 2 = Topics button (when a category is selected), Format selector and Sort selector sharing the width (`flex: 1 1 0` each, min 120px, wrap allowed); the view switch sits at the end of row 2. Reset appears at the end of row 2 when active.

All spacing, radii and sizes come from Astryx tokens; no hard-coded px other than the three widths above.

Done means: build and smoke pass; 2x screenshot of the toolbar region at 1280 on `/browse?category=Computer%20Science%20Fundamentals&topic=Programming%20Languages/Go` with and without a query, and at 375; every control measured at the same height (report the heights).
