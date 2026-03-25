# Workspace Implementation Plan

## Source of truth

- Superdesign project: `0e542410-b834-442c-98b7-89e31fdcbbd0`
- Superdesign draft: `334441f1-f8fb-4716-9bd2-c5bdec4fb495`
- Verified on `2026-03-25` that the fetched draft matches `docs/design/html/workspace.html` exactly.

## Goal

Implement the workspace page so it behaves like the approved Superdesign draft, especially on the left-side stream:

- the workspace fills the viewport
- the stream itself scrolls
- the post composer stays pinned below the stream
- the only persistent user avatar stays at the bottom of the global sidebar
- the header does not introduce a second user-profile block that pulls identity UI upward

## Current gaps against the draft

1. `templates/components/page_header.html`
   The current header includes an authenticated user card in the top-right area. The draft component contract does not expose a user-profile prop, and the approved workspace chrome is designed around the bottom sidebar avatar as the persistent identity anchor.

2. `templates/pages/workspace.html`
   The page is structurally close to the draft, but it should be treated as a strict viewport shell, not a normal document page. Scroll ownership and footer/composer ownership need to be implemented exactly like the draft.

3. `templates/components/global_sidebar.html`
   The sidebar already places the avatar below the navigation, but it only works as intended when the parent shell height is fully constrained by the workspace viewport.

4. `templates/base.html`
   The base layout does not currently expose a clean workspace-only body/shell variant. The workspace implementation should avoid changing global page behavior for dashboard, assumptions, history, and other routes.

## Implementation plan

### 1. Add a workspace-specific chrome variant

Files:

- `templates/components/page_header.html`
- `projects/views.py` or the context-building layer that feeds header state

Work:

- Add a workspace-specific header mode instead of changing the shared header globally.
- In workspace mode, remove the top-right authenticated user card.
- Keep the draft-aligned breadcrumb, status label, unresolved/team information, and action buttons.
- Preserve the existing richer header behavior for non-workspace routes unless separately redesigned.

Reason:

This prevents the UI from showing two identity anchors at once and restores the draft's intended bottom-sidebar avatar behavior.

### 2. Make workspace a true viewport app surface

Files:

- `templates/pages/workspace.html`
- potentially `templates/base.html` if a body-class or body-attribute block is needed

Work:

- Match the draft shell exactly: root workspace container should own the viewport height and clip page-level overflow.
- Ensure only the left stream and right spec panes scroll.
- Keep the composer outside the stream scroller.
- Keep the split handle and right-pane top gradient in the same ownership structure as the draft.

Reason:

If the page itself scrolls, the composer stops behaving like a pinned footer and the sidebar avatar no longer reads as anchored to the app frame.

### 3. Reproduce the left stream DOM more literally

Files:

- `templates/pages/workspace.html`

Work:

- Keep the thread header, stream scroller, and composer as three sibling blocks in one flex column.
- Match the draft class ordering and spacing for the composer wrapper:
  `p-4 border-t border-gray-200 bg-gray-50`
- Match the inner composer shell styling and button spacing to the draft, including icon button treatment.
- Re-add the filter tab icon treatment from the draft if visual parity is the goal.

Reason:

This page is close enough that another abstract "layout fix" is risky. A more literal draft-to-template port is safer.

### 4. Keep the sidebar avatar as the single persistent identity anchor

Files:

- `templates/components/global_sidebar.html`

Work:

- Keep the avatar after the `flex-1` navigation block so it naturally sits at the bottom.
- Do not add header-level identity UI on the workspace route.
- Validate spacing against the draft once the viewport shell is corrected.

Reason:

The sidebar avatar position is correct only when the surrounding shell is correct and there is no competing avatar higher on the page.

### 5. Introduce route-safe implementation hooks

Files:

- `templates/base.html`
- `projects/views.py`
- any shared context processor used by the page header

Work:

- Prefer an explicit workspace flag such as `page_variant = "workspace"` or `header_variant = "workspace"` over brittle path checks inside templates.
- If body-level behavior is required, expose a template block or context-driven class instead of hardcoding `h-screen overflow-hidden` globally.

Reason:

The workspace needs app-like overflow behavior, but most other pages in this project are standard scroll pages.

## Verification plan

1. Compare the final DOM structure and classes against `docs/design/html/workspace.html`.
2. Confirm there is no body scroll on the workspace route at desktop sizes.
3. Confirm the left stream scrolls independently and the composer never scrolls away.
4. Confirm the only persistent user avatar is the sidebar avatar at the bottom of the rail.
5. Run `uv run python manage.py check`.
6. Run `npm run build:css` if any new Tailwind classes or component-layer utilities are introduced.

## Acceptance criteria

- Workspace visually behaves like the approved Superdesign draft.
- The composer is pinned below the stream and remains visible while the stream scrolls.
- The top header no longer shows an extra user-profile card on the workspace page.
- The sidebar avatar is visually anchored to the bottom of the left rail.
- Other routes keep their current scroll behavior unless explicitly updated.

## Non-blockers

- `.superdesign/init/extractable-components.md` is not present. That does not block implementation planning, but it should be added later if we want to mirror the Superdesign component extraction workflow more strictly.
