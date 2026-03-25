# SpecBridge Design System

## Product Context
- SpecBridge is a collaborative, agent-assisted spec refinement platform.
- The UI should feel like a premium operations workspace rather than a generic document editor.
- Every screen must reinforce iteration, traceability, versioning, and cross-functional alignment.

## Typography
- Primary text: `Satoshi`
- Display headings: `Cabinet Grotesk`
- Tone: crisp, editorial, dense, and executive-facing

## Core Palette
- `gray-50`: `#FAFAFA`
- `gray-100`: `#F4F4F5`
- `gray-200`: `#E4E4E7`
- `gray-300`: `#D4D4D8`
- `gray-400`: `#A1A1AA`
- `gray-500`: `#71717A`
- `gray-600`: `#52525B`
- `gray-700`: `#3F3F46`
- `gray-800`: `#27272A`
- `gray-900`: `#18181B`
- `brand.agent`: `#8B5CF6`
- `brand.decision`: `#10B981`
- `brand.warning`: `#F59E0B`
- `brand.danger`: `#EF4444`
- `brand.info`: `#3B82F6`

## Layout Patterns
- Global shell: slim left sidebar, full-width top header, content canvas on `gray-50`
- Cards: white panels, subtle border, soft shadow, 20px to 28px radius
- Split workspaces: hard dividers with thin gray borders, no heavy separators
- Tables and diff views: restrained, paper-like, dense typography

## Component Rules
- Sidebar uses icon-only navigation with one strong active state.
- Header carries breadcrumb, project status, unresolved count, and team presence.
- Status must always be visible using small uppercase chips or bordered pills.
- Agent UI uses purple accents only for guidance, never as the primary page color.
- Timeline items must show chronological order, status, origin, and override relationships.
- Exports always render from a pinned version state, not mutable live content.

## Motion & Feedback
- Keep transitions subtle: hover border shifts, soft shadow changes, opacity adjustments.
- Polling is page-level and low-key; no chatty live indicators beyond status labels.

## Added Gap Pages
- `Assumptions Register` and `Members & Roles` must use the same chrome, card treatment, and typography as drafted pages.
- Gap pages should look native to the drafted system, not like admin screens.

