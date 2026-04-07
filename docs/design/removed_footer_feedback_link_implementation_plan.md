# Removed Footer Feedback Link Implementation Plan

## Source of truth

- Superdesign project: `0e542410-b834-442c-98b7-89e31fdcbbd0`
- Superdesign draft: `334441f1-f8fb-4716-9bd2-c5bdec4fb495`
- Draft title verified on `2026-04-07`: `Removed Footer Feedback Link`
- Saved artifacts refreshed from the live draft on `2026-04-07`:
  - `docs/design/html/workspace_removed_footer_feedback_link.html`
  - `docs/design/screenshots/removed_footer_feedback_link.png`

## Goal

Match the latest approved sidebar affordance pattern from Superdesign:

- keep document and composer surfaces free of footer-level feedback links
- place the new sidebar affordance in the bottom user cluster
- render that affordance above the avatar, not as an overlapping badge

## Current assessment

### Already aligned

1. There is no footer feedback link in the Django templates.
   - A repo scan across `templates/` and `static/js/` shows no feedback CTA anchored to the bottom of the workspace document.

2. There is no feedback keyboard shortcut handler in the current frontend runtime.
   - `static/js/app.js` contains modal, autosave, nav, and action handlers, but no feedback shortcut binding.

3. The project settings modal already exists as the natural sidebar destination.
   - `templates/components/project_settings_modal.html`
   - `templates/components/project_settings_form_surface.html`

### Remaining design gap

1. The bottom sidebar affordance must live above the avatar, not on top of it.
   - The Superdesign screenshot shows a vertically stacked bottom cluster:
     - settings-style affordance
     - user avatar
   - The control is visually adjacent to the avatar, but not attached as a floating overlay badge.

## Recommended implementation

### 1. Restack the bottom sidebar cluster

Files:

- `templates/components/global_sidebar.html`

Work:

- keep the authenticated bottom cluster as a vertical stack
- render the project settings trigger before the avatar
- remove absolute positioning from the trigger so it no longer overlaps the avatar bounds

Reason:

This is the primary visual delta between the current implementation and the approved draft.

### 2. Keep the settings trigger visually secondary

Files:

- `templates/components/global_sidebar.html`
- optionally `static_src/styles/tailwind.css` if shared styling becomes necessary later

Work:

- style the trigger like a small sidebar utility action, not a primary CTA
- preserve neutral gray tones and light hover treatment consistent with the sidebar rail
- avoid introducing extra labels or badge chrome into the bottom cluster

Reason:

The draft treats this as a utility affordance, not as a callout.

### 3. Preserve the footer-clean contract

Files:

- `templates/pages/workspace.html`
- `static/js/app.js`

Work:

- do not add any new footer feedback link to the composer or document pane
- do not add a feedback keyboard shortcut unless a later design explicitly restores one
- keep future project-level preferences routed through the sidebar-triggered modal

Reason:

The draft’s stated intent is to remove footer-level feedback entry and consolidate that affordance into the sidebar.

## Verification plan

1. Confirm the bottom sidebar cluster renders as:
   - settings trigger
   - avatar
2. Confirm the trigger no longer overlaps the avatar box at any breakpoint.
3. Confirm the workspace page still shows no footer feedback link near the composer or document canvas.
4. Confirm `static/js/app.js` has no feedback shortcut handler.
5. Run `npm run build:css`.

## Acceptance criteria

- The bottom-left sidebar cluster matches the draft’s vertical relationship more closely.
- The project settings trigger is above the avatar, not overlaid on it.
- No footer feedback link or feedback shortcut exists in the shipped UI.
