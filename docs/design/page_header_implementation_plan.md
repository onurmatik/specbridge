# Page Header Implementation Plan

## Source of truth

- Superdesign project: `0e542410-b834-442c-98b7-89e31fdcbbd0`
- Superdesign draft: `334441f1-f8fb-4716-9bd2-c5bdec4fb495`
- Superdesign component: `PageHeader` (`d1c411f2-4007-453c-ac17-8de1723af111`)
- Verified on `2026-04-06` by fetching the live component definition from:
  - `https://api.superdesign.dev/v1/design-drafts/334441f1-f8fb-4716-9bd2-c5bdec4fb495/components`

## Requirement

The navbar in scope is the site-wide top header component, not the workspace document-section navbar.

This plan covers the reusable header rendered from:

- `templates/components/page_header.html`

## Superdesign component contract

The live Superdesign `PageHeader` is materially different from the current Django template.

It is a single-row `h-16` toolbar with:

- breadcrumb links on the left
- a thin vertical divider
- inline project status text with an unresolved-count indicator
- a compact avatar stack on the right
- two compact actions: `History` and `Export Spec`

It does not include:

- a second-row page title block
- a top-right user identity card
- the large team/open-items metric card
- the `API`, `Open Workspace`, and `Log Out` button cluster currently rendered by the app

## Current gaps against the design

1. `templates/components/page_header.html`

   The current header is effectively a two-row information block:

   - breadcrumb line
   - page title line
   - optional status and AI badges near the title
   - metric card on the right
   - user profile card on the right
   - project and auth actions on the right

   That structure does not match the Superdesign component's height, density, or information hierarchy.

2. `projects/services.py`

   The workspace context currently feeds header-specific content such as:

   - `page_title = "Workspace"`
   - `page_breadcrumb_label = "Workspace"`
   - `header_hide_project_identity = True`

   This pushes the header away from the design's project-identity contract and turns it into a route-title surface instead of a reusable project toolbar.

3. Shared page templates

   Multiple pages assume the header can absorb route identity and actions. If the header is reduced to the design's compact toolbar, some title and action responsibilities will need to move into page-local hero rows instead of staying in the global header.

4. `static_src/styles/tailwind.css`

   The shared button and badge primitives are useful, but the header currently relies on generic component classes rather than a stricter header-specific token set. That makes pixel-level matching difficult.

## Implementation plan

### 1. Introduce an explicit header variant contract

Files:

- `templates/components/page_header.html`
- `projects/services.py`
- `projects/views.py`

Work:

- Add an explicit `header_variant` or `page_header_variant` context value.
- Use a dedicated design-aligned variant for project routes.
- Keep create/auth/no-project flows on a separate variant instead of overloading one template branch with many conditionals.

Reason:

The current template mixes at least three different header jobs into one component. A variant contract is the safest way to move toward the design without breaking non-project pages.

### 2. Rebuild the project-route header to match the Superdesign component

Files:

- `templates/components/page_header.html`

Work:

- Convert the project header into a compact single-row shell:
  - `h-16`
  - `px-6`
  - `border-b border-gray-200`
  - `bg-white`
- Rework the left side into:
  - breadcrumb
  - divider
  - inline status indicator with unresolved-count copy
- Remove the current second-row title treatment from the project-route header variant.
- Remove the top-right metric card and user card from this design-aligned variant.

Reason:

The largest fidelity issue is not a spacing tweak. The component structure itself is different.

### 3. Move page titles and route-local actions out of the global header where needed

Files:

- `templates/pages/workspace.html`
- `templates/pages/dashboard.html`
- `templates/pages/decisions.html`
- `templates/pages/history.html`
- `templates/pages/handoff.html`
- any other page that currently depends on the header as its title surface

Work:

- Treat the global header as project chrome, not as the main page heading.
- Render route-local titles and route-specific CTAs inside page content, directly below the header, where the design requires them.
- Revisit the workspace route specifically, because it currently uses `Workspace` as header identity while the design header is project-oriented.

Reason:

Trying to keep the existing big title row inside the header will block a faithful implementation.

### 4. Replace the current right-side action cluster with a design-aligned action model

Files:

- `templates/components/page_header.html`
- `projects/services.py`
- possibly the route context builders that determine page actions

Work:

- Replace the current `API`, `Open Workspace`, and `Log Out` layout for the design-aligned project variant.
- Add support for the compact design actions:
  - `History`
  - primary action such as `Export Spec`
- Add support for the avatar stack as a compact presence indicator.
- Decide whether logout should move into sidebar/profile UI instead of staying in the header.

Reason:

The existing right side is visually heavier and semantically different from the design component.

### 5. Normalize header data around project identity instead of route identity

Files:

- `projects/services.py`
- any shared context function that feeds `page_header.html`

Work:

- Feed the design header with project-oriented values:
  - projects link
  - current project label and URL
  - status label
  - unresolved count
  - participant presence data
- Reduce usage of `page_breadcrumb_label` and `header_hide_project_identity` for project routes.
- Reserve route labels like `Workspace` or `History` for page-local headings unless a non-project header variant explicitly needs them.

Reason:

The live Superdesign component is centered on project context, not page context.

### 6. Add header-specific primitives if generic buttons are not enough

Files:

- `static_src/styles/tailwind.css`

Work:

- Introduce small header-scoped utility classes only if needed for exact sizing, spacing, and avatar-stack behavior.
- Keep these scoped to the header component rather than stretching `.primary-button` and `.secondary-button` to fit every case.

Reason:

Pixel-perfect header work becomes brittle when generic primitives are forced to serve both page CTAs and compact toolbar actions.

## Verification plan

1. Compare the rebuilt `page_header.html` structure against the fetched Superdesign `PageHeader` HTML.
2. Confirm the project-route header renders as a single-row `h-16` toolbar.
3. Confirm the left side shows breadcrumb, divider, and inline status instead of a stacked title block.
4. Confirm the right side no longer renders the large metric card and user card in the design-aligned variant.
5. Confirm route-local titles still appear clearly in page content after the header is compacted.
6. Run `npm run build:css`.
7. Run `uv run python manage.py check`.

## Acceptance criteria

- The site-wide project header visually matches the Superdesign `PageHeader` component more closely than the current implementation.
- The project header is a compact toolbar, not a two-row title surface.
- Header responsibilities are clearly separated from page-content heading responsibilities.
- Non-project routes keep a safe fallback variant and do not regress.
