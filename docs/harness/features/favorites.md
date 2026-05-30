# Favorites Feature Notes

Date: 2026-05-30

## Current Behavior

Users can mark assets as favorites from category asset lists or from the asset detail header. Favorites are stored in browser `localStorage` through a small Zustand store, so they persist for the same browser without requiring a backend schema change.

The category list shows a favorites panel on the right side of the asset list. Clicking a favorite navigates directly to `/detail/:ticker`.

## Ownership Map

- Favorite state: `frontend/src/store/favoriteStore.js`
- Favorite toggle and right-side panel: `frontend/src/pages/CategoryView.jsx`
- Detail page favorite toggle: `frontend/src/pages/AssetDetail.jsx`
- Asset display names and ticker fallback: `frontend/src/utils/constants.js`, `frontend/src/utils/formatters.js`

## Data Flow

1. `favoriteStore.js` reads the `favoriteAssets` localStorage key at app startup.
2. Category rows call `toggleFavorite` with `symbol`, display `name`, and `categoryKey`.
3. The detail page can also call `toggleFavorite` for the current ticker.
4. The category favorite panel reads the shared `favorites` array and routes clicks to `/detail/:ticker`.
5. Removing a favorite updates Zustand state and writes the updated array back to localStorage.

## Contracts

- localStorage key: `favoriteAssets`
- Favorite shape:
  - `symbol`
  - `name`
  - `categoryKey`
- Detail route used by favorites: `/detail/:ticker`

## Change Rules

- Do not store sensitive user data in favorites.
- If favorites become account-synced, add backend models/routes deliberately and document migration or fallback behavior.
- Keep route encoding intact when navigating to tickers such as `KRW=X`, `^GSPC`, or Korean stock codes.

## Verification

- Frontend build from `frontend/`: `npm run build`
- Frontend lint from `frontend/`: `npm run lint`
- Manual browser check: toggle a category row star, reload, click a favorite, and confirm the detail page opens.

## Change Records

- `docs/harness/asset-favorites.md`

## Open Risks

- Favorites are browser-local and are not synced between devices or user accounts.
