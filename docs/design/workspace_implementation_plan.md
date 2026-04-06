# Workspace Implementation Plan

## Source of truth

- Superdesign project: `0e542410-b834-442c-98b7-89e31fdcbbd0`
- Superdesign draft: `334441f1-f8fb-4716-9bd2-c5bdec4fb495`
- Live draft title on 2026-04-06: `Dynamic Horizontal Navbar & Extended Spec`
- Saved artifact refreshed from the live draft on 2026-04-06:
  - `docs/design/html/workspace.html`

## Goal

Align the workspace page more literally to the approved Superdesign draft, with the left pane as the first priority:

- make the conversation side read like a single polished alignment stream
- keep the composer pinned below the stream
- preserve the existing SpecBridge editing and AI workflows where they already exceed the draft
- close only the real backend gaps, not imagined ones

## Current assessment

### What is already aligned or backend-ready

1. The workspace route already behaves like an app shell.
   - `templates/pages/workspace.html` already owns viewport height and keeps the left and right panes independently scrollable.

2. The workspace header is no longer blocked by an extra top-right identity card.
   - `projects/services.py` sets `header_variant = "project-toolbar"` for project pages.
   - `templates/components/page_header.html` renders the compact project toolbar in that mode.

3. The sidebar already matches the intended identity anchor pattern.
   - `templates/components/global_sidebar.html` keeps the user avatar below the `flex-1` nav block.

4. The right pane already has stronger functionality than the draft.
   - Section autosave exists.
   - Section status updates exist.
   - AI revise exists.
   - Section insert, move, and delete exist.

5. Concern and stream actions are already backed by APIs.
   - Stream post create: `alignment/api.py`
   - Concern scan / re-evaluate / dismiss / resolve-with-AI: `specs/api.py`
   - Proposal accept / reject: `specs/api.py`

6. Dynamic section navigation is partially implemented already.
   - `templates/pages/workspace.html` renders a horizontal section nav.
   - `static/js/app.js` already handles section scroll-to and scroll spy.

## Gap verdict

There is no major backend or schema gap between the latest draft and the current product.

The main gap is a frontend composition gap:

- the left pane is structured as multiple product surfaces
- the draft expects a single conversation-first stream
- the right pane is functionally ahead of the draft, but still missing a few chrome details

The only likely backend or API additions are optional, not mandatory:

- draft-specific quick actions if we want exact CTA semantics
- a persisted split width if we want a truly resizable divider instead of a visual handle

## Concrete gaps against the latest draft

### 1. Left pane composition is still product-heavy instead of stream-first

Current structure in `templates/pages/workspace.html`:

- queue summary
- selected concern summary card
- alignment stream
- AI patch review
- pinned composer

Draft structure:

- compact stream header
- filter tabs
- one mixed, chronologically readable conversation stream
- pinned composer immediately below it

Impact:

- the current page exposes more functionality than the draft, but the visual hierarchy is off
- this is the biggest reason the left side does not feel pixel-perfect

### 2. The draft filter model does not exist yet

Latest draft expects:

- `All`
- `Decisions`
- `Open`

Current template shows static labels instead:

- `Queue`
- `Alignment Stream`
- `Posting / AI Chat`

Missing today:

- no `stream` query param
- no client-side filter state
- no server-side filtered view model for those three states

### 3. The unified stream view model is missing

`alignment/services.py::build_workspace_entries()` currently mixes:

- top-level stream posts
- non-pending decisions

It does not build a single draft-shaped stream item list containing:

- human messages with avatar treatment
- agent intervention cards
- open concern cards
- selected concern thread messages
- AI patch review summaries

Impact:

- backend data exists, but the presentation layer is not yet organized around the draft

### 4. Draft quick actions do not map 1:1 to current endpoints

Examples from the draft:

- `Address Existing Users`
- `Define SSO Strategy`
- `Resolve`

Current product actions are different:

- `Raise concern`
- `Re-evaluate`
- `Resolve with AI`
- proposal `Accept` / `Reject`

Recommendation:

- v1 should map draft quick actions to existing behaviors where possible
- do not add new endpoints unless a button truly needs unique side effects

### 5. Actor presentation is incomplete on the left side

The draft relies on:

- human avatars
- a clear agent visual treatment
- decision cards inline in the stream

Current implementation:

- usually renders text-first cards without avatar rhythm
- separates concern and proposal surfaces from the main stream

Backend note:

- `alignment.models.StreamPost` already keeps `author`, `actor_name`, and `actor_title`
- for user-authored entries, avatar rendering can usually be derived from `author.avatar_url`
- AI and system entries still need explicit icon or fallback treatment in the view model

### 6. Right-pane chrome is close, but not fully aligned to the latest draft

Still missing or only partially present:

- nav fade overlays on both sides of the horizontal section nav
- hidden horizontal scrollbar treatment
- active nav item auto-centering while scrolling
- visual split handle between left and right panes

These are frontend-only gaps.

### 7. The previously saved design artifact was stale

On 2026-04-06, the live draft differed from the older checked-in `docs/design/html/workspace.html`.

That artifact has now been refreshed so implementation work can compare against the latest approved draft rather than an older snapshot.

## Recommended implementation sequence

### Phase 1. Close the low-risk chrome gaps first

Files:

- `templates/pages/workspace.html`
- `static/js/app.js`
- optionally `static_src/styles/tailwind.css` if a tiny utility is cleaner than repeated classes

Work:

- replace the current left-side header copy and static tab labels with the draft language
- keep the pinned composer, but restyle it to the draft shell more literally
- add the visual split handle between panes
- add nav fade overlays and hidden scrollbar styling for the right-side horizontal nav
- update JS so the active nav item is kept centered when scroll spy changes state

Reason:

- this gets visible pixel alignment quickly without disturbing any backend behavior

### Phase 2. Introduce a draft-shaped workspace stream builder

Files:

- `alignment/services.py`
- `projects/services.py`
- `templates/pages/workspace.html`

Work:

- add a `stream_filter` input to `workspace_context()`
- build a new `workspace_stream_items` list that can represent:
  - `message`
  - `agent_notice`
  - `decision`
  - `open_concern`
  - `proposal_summary`
- keep current raw collections during migration so the page can switch incrementally
- use the builder to feed the left pane rather than manually stacking unrelated cards

Reason:

- the live draft is essentially a stream composition problem, not a database problem

### Phase 3. Make the three draft filters real

Files:

- `projects/views.py`
- `projects/services.py`
- `templates/pages/workspace.html`

Work:

- accept `?stream=all|decisions|open`
- highlight the active filter server-side for deterministic first render
- filter `workspace_stream_items` by type or concern status

Recommended behavior:

- `All`: full mixed stream
- `Decisions`: decision items only
- `Open`: open concerns and unresolved agent/question items

Reason:

- a URL-driven filter is shareable, testable, and works without client hydration

### Phase 4. Decide how current advanced features should survive the redesign

Features that exist today but are not primary in the draft:

- Active Queue
- selected concern detail card
- AI Patch Review

Recommendation:

- do not remove the backend support
- reduce their default visual dominance on the workspace route
- move them behind contextual expansions or fold them into the stream model

Suggested v1:

- selected concern becomes a focused stream state, not a large standalone card
- AI Patch Review becomes an expandable review block tied to the selected concern
- queue data powers the `Open` filter instead of always occupying top-of-pane space

### Phase 5. Map draft quick actions onto existing product behaviors

Files:

- `templates/pages/workspace.html`
- `static/js/app.js`
- optionally `projects/services.py` if button metadata should be computed server-side

Work:

- use existing endpoints wherever possible
- prefer lightweight behaviors first:
  - selecting a concern
  - scrolling the composer into view
  - prefilling the composer with a prompt
  - opening the concern review state

Avoid for v1:

- adding new endpoints just to mimic draft button labels

Reason:

- the backend already covers the important workflows; only the interaction packaging is missing

## Verification plan

1. Compare the final workspace DOM and spacing against `docs/design/html/workspace.html`.
2. Confirm there is no body scroll on `/projects/<slug>/workspace/`.
3. Confirm the left stream scrolls independently and the composer remains visible.
4. Confirm `?stream=all`, `?stream=decisions`, and `?stream=open` render the expected states.
5. Confirm the right-side horizontal nav:
   - highlights the current section
   - stays horizontally usable with many sections
   - recenters the active tab during scroll spy updates
6. Confirm concern actions, proposal actions, and spec autosave still work after the DOM restructure.
7. Run:
   - `uv run python manage.py check`
   - `uv run python manage.py test alignment.tests specs.tests`

## Acceptance criteria

- The left pane reads as one coherent alignment stream instead of several stacked tools.
- The composer remains pinned below the stream.
- The latest draft's three filter states are real and navigable.
- Existing concern and spec workflows still function.
- The right pane preserves current editing power while matching the latest draft chrome more closely.

## Non-blockers

- A truly draggable split layout is optional; a visual handle is enough for the first pass.
- Exact sample content from the Superdesign mock should not replace real project data.
- No database migration is required for the recommended implementation sequence.
