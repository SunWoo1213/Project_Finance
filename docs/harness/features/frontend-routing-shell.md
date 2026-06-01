# Frontend Routing, Shell, Shared UI, And State Feature Notes

Date: 2026-05-30

## Current Behavior

The frontend is a React Vite JavaScript app. `App.jsx` owns the route table and app shell. `Header.jsx` provides global navigation. Route pages own most data fetching, while shared components, stores, and utilities keep reusable display behavior out of pages.

Current routes:

- `/`: home market summary.
- `/category/:type`: category list.
- `/market/:ticker`: main index/FX time-based snapshot with a related dashboard link.
- `/detail/:ticker`: asset detail, AI report, and comments.
- `/login`: Google login.
- Planned subscription routes: `/pricing`, `/billing/success`, and `/billing/cancel`.

## Ownership Map

- Route composition and shell: `frontend/src/App.jsx`
- Entry point: `frontend/src/main.jsx`
- Global navigation: `frontend/src/components/Header.jsx`
- Shared components: `frontend/src/components/`
- Global auth state: `frontend/src/store/authStore.js`
- Global chat state: `frontend/src/store/chatStore.js`
- Browser-local favorite state: `frontend/src/store/favoriteStore.js`
- Constants and display helpers: `frontend/src/utils/constants.js`, `frontend/src/utils/formatters.js`
- Shared route context/API helpers: `frontend/src/utils/chatContext.js`, `frontend/src/utils/apiClient.js`
- Page-level screens: `frontend/src/pages/`

## Data Flow

1. `main.jsx` mounts the React tree.
2. `App.jsx` wraps routes with the persistent layout and toast provider.
3. `Header.jsx` reads auth state and renders navigation.
4. Pages fetch their own data and pass display values to reusable components when appropriate.
5. `favoriteStore.js` keeps browser-local favorite assets in sync with localStorage for category and detail screens.
6. `ChatbotLauncher.jsx` is mounted globally and overlays the current route without changing route page ownership.
7. Planned tier behavior should render `ChatbotLauncher` only for active Pro users.
8. `chatStore.js` keeps session-only chat messages and pending/error state.
9. Shared utility functions format prices, tickers, changes, and display names.

## Contracts

- Pages should own route-specific loading and error states.
- Components should generally receive props rather than calling APIs directly.
- Zustand store should contain only state shared across screens.
- Utility functions should stay pure and avoid DOM, React state, localStorage, or API calls.

## Change Rules

- Preserve React + Vite + JavaScript unless the user explicitly asks for migration.
- Do not introduce a new router, design system, or global state framework without approval.
- When adding routes, update `App.jsx`, navigation if needed, the relevant page documentation, and this feature document.
- When removing a route, update linked docs and change records so future agents do not re-add dead UI.

## Verification

- Frontend build from `frontend/`: `npm run build`
- Frontend lint from `frontend/`: `npm run lint` when feasible, noting pre-existing lint findings if they remain.
- For route changes, start the dev server and verify navigation when the change affects user flow.

## Change Records

- `docs/harness/harness-feature-documentation.md`
- `docs/harness/google-login-only.md` removed the `/register` route and signup navigation.
- `docs/harness/main-market-snapshot-and-news.md` added `/market/:ticker` for home index/FX cards.
- `docs/harness/asset-favorites.md` added browser-local favorite asset state and navigation.
- `docs/harness/chatbot-feature-implementation-2026-05-31.md` added the global chatbot launcher, panel, session state, and route action handling.
- `docs/harness/subscription-tier-payment-plan-2026-06-01.md` plans pricing/billing routes and tier-based report/chatbot gates.

## Open Risks

- API base URLs are duplicated in page code.
- Some page components, especially asset detail, carry enough responsibility that future work should consider focused extraction.
