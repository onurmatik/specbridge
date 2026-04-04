# No-Project Entry Implementation Plan

## Source of truth

- Superdesign project: `0e542410-b834-442c-98b7-89e31fdcbbd0`
- Reviewed drafts:
  - `334441f1-f8fb-4716-9bd2-c5bdec4fb495` (`Align - Project Spec Workspace`)
  - `1f49067a-c64b-4ffe-94be-8aa717bddd1e` (`Team Alignment Dashboard`)
- Repo note in `docs/design/README.md` already confirms that the current project directory is a derived page, not an original Superdesign draft.

## Requirement

After login, a user with no active projects should not land on a mixed-purpose directory surface.

They should either:

1. land directly on a `Create Project` form page, or
2. see a single, unmistakable primary CTA: `Create Project`

## Recommendation

Use a dedicated authenticated `Create Project` entry page and treat it as the canonical no-project destination.

Reason:

- it satisfies the stricter version of the requirement directly
- it reuses the existing modal content with minimal visual redesign
- it removes the current ambiguity caused by multiple create triggers, directory chrome, and side panels competing for attention
- it keeps the project directory focused on listing and switching between existing projects

## Current state in the codebase

### Redirect behavior

- `accounts/views.py`
  - `_post_auth_redirect_target()` falls back to `project-directory` when the user has no accessible project.
- `projects/views.py`
  - `project_directory()` renders the same page for both:
    - users with active projects
    - authenticated users with zero active projects
  - `shortcut_redirect()` also sends no-project users back to the directory.

### UI behavior

- `templates/pages/project_directory.html`
  - authenticated no-project state shows a hero CTA
  - the page header also shows `Create Project`
  - the empty list state also shows `Create Project`
  - the right rail still renders supporting panels
- `templates/components/create_project_modal.html`
  - the actual form already exists, but only as a modal
- `templates/components/page_header.html`
  - adds another `Create Project` trigger when `project` is empty
- `static/js/app.js`
  - assumes a single global create form and a modal-driven create flow

This means the current experience violates the "single clear action" requirement even before any visual polish work.

## Design direction

There is no original Superdesign draft for the no-project page. The implementation should therefore borrow the approved shell language from the fetched workspace/dashboard drafts:

- same `GlobalSidebar` rail
- same `PageHeader` typography and badge language
- same `Satoshi` + `Cabinet Grotesk` pairing
- same card radii, border tones, white-on-gray surface treatment
- same restrained accent usage: purple for agent/system framing, green for success, amber/red for risk states

The easiest way to stay consistent is to promote the existing split create modal into a full-page surface.

## Implementation plan

### 1. Add a dedicated create route and view

Files:

- `projects/urls.py`
- `projects/views.py`

Work:

- Add a dedicated route such as `projects/create/` with a named URL like `project-create`.
- Render a dedicated authenticated entry page for project creation.
- Keep the route usable for authenticated users generally, not only zero-project users, so it can become the canonical "new project" surface.

Reason:

This removes the need to overload the directory page with two jobs: list existing workspaces and bootstrap a first one.

### 2. Make no-project login land on the create route

Files:

- `accounts/views.py`
- `projects/views.py`

Work:

- Update `_post_auth_redirect_target()` so that when the resolved redirect would land on the directory and the user has no visible projects, it returns `project-create`.
- Apply the same fallback when the requested slug is inaccessible and the user still has no primary project.
- Update `shortcut_redirect()` so authenticated no-project users go to `project-create` instead of returning to the directory.
- Decide whether `project_directory()` should hard-redirect authenticated zero-project users to `project-create`.
  - Recommended: yes, to keep one canonical entry path.

Reason:

Without redirect changes, the new page exists but the actual login experience still lands on the old ambiguous screen.

### 3. Extract the create form into a reusable partial

Files:

- `templates/components/create_project_modal.html`
- new partial such as `templates/components/create_project_form_surface.html`
- new page such as `templates/pages/project_create.html`

Work:

- Move the split create content out of the modal wrapper into a reusable partial.
- Reuse the same content inside:
  - the new dedicated page
  - the existing modal, if the modal is retained for users who already have projects
- Keep the current copy and benefits list as the initial baseline unless product wants tighter wording.

Reason:

This avoids maintaining two diverging versions of the same create flow.

### 4. Simplify the no-project UI to one primary action

Files:

- `templates/pages/project_create.html`
- `templates/components/page_header.html`
- optionally `templates/pages/project_directory.html`

Work:

- On the dedicated create page, show the form immediately above the fold.
- Avoid a second `Create Project` trigger in the header when the page itself is already the create flow.
- If the directory remains reachable for zero-project users, remove all duplicate create triggers from that state and leave only one primary CTA.
- Treat side panels like `Gap Closers` and `Workspace Flow` as secondary or remove them entirely from the no-project path.

Reason:

The requirement is about decision clarity, not just visual consistency. Duplicate CTAs and secondary cards reintroduce hesitation.

### 5. Refactor the JS so create works in page and modal contexts

Files:

- `static/js/app.js`

Work:

- Stop relying on global singletons for:
  - `[data-project-create-form]`
  - `[data-project-errors]`
  - `[data-project-submit]`
- Scope error rendering and submit-state handling to the active form instance.
- Keep session-storage draft persistence, but make hydration target the currently opened form surface.
- If the dedicated page replaces the modal for no-project users, keep modal open/close code only for the "create additional project" case.

Reason:

The current JS is written for exactly one create form in the DOM. Reusing the flow on a full page will become brittle unless the selectors are localized.

### 6. Keep the directory focused on existing projects

Files:

- `templates/pages/project_directory.html`
- `templates/components/page_header.html`

Work:

- Optimize the directory for users who already have projects:
  - project list
  - latest project shortcuts
  - optional create-new entry point
- Remove no-project-specific explanatory copy from the main directory template once the dedicated create route is canonical.

Reason:

This restores a clear information architecture:

- directory = browse/switch projects
- create page = bootstrap first project

### 7. Update test coverage around the new entry behavior

Files:

- `accounts/tests.py`
- `projects/tests.py`

Work:

- Update tests that currently expect `project-directory` plus `No projects yet` after login/signup.
- Add coverage for:
  - login of a no-project user redirects to `project-create`
  - signup of a no-project user redirects to `project-create`
  - authenticated no-project access to `/dashboard/` and similar shortcuts redirects to `project-create`
  - project creation from the dedicated page still redirects to the new workspace route

Reason:

The redirect contract is the real product requirement here; it should be enforced at the test layer.

## Acceptance criteria

- After login, a user with zero active projects lands on the dedicated create page.
- The create form is visible without opening a modal.
- The no-project path exposes one primary action only: `Create Project`.
- The existing project directory remains optimized for users who already have projects.
- Creating a project still ends at `/projects/<slug>/workspace/`.

## Lower-scope fallback

If the team wants a smaller first pass, keep the directory route but simplify the authenticated zero-project branch so it renders:

- one hero block
- one primary CTA
- no duplicate header CTA
- no duplicate empty-state CTA
- no right-rail supporting cards

This is cheaper, but it is still weaker than a dedicated create page because the actual form remains hidden behind a second interaction.
