# Asset Favorites

Date: 2026-05-30

## Objective

Allow users to favorite individual assets and quickly open favorite assets from the asset list screen.

## Files Changed

- `frontend/src/store/favoriteStore.js`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/store/DEVELOPMENT_DIRECTION.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/favorites.md`

## Behavior Changes

- Category rows now include a rightmost star button for adding or removing favorites.
- Category pages show a right-side favorites panel.
- Clicking a favorite navigates directly to `/detail/:ticker`.
- Asset detail headers include a favorite toggle for the current ticker.
- Favorites persist in browser `localStorage` under `favoriteAssets`.

## Verification Performed

- `npm.cmd run lint` from `frontend/`: passed.
- `npm.cmd run build` from `frontend/`: passed. Vite reported a large chunk warning after successful build.

## Follow-Up Risks

- Favorites are local to the browser. Account-synced favorites would require a backend model, API routes, and migration planning.
