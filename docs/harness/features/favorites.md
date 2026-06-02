# Favorites Feature Notes

Date: 2026-05-30

## Current Behavior

Users can mark assets as favorites from category asset lists or from the asset detail header. Favorites are stored in browser `localStorage` through a small Zustand store, so they persist for the same browser without requiring a backend schema change.

The category list shows a favorites panel on the right side of the asset list. Clicking a favorite navigates directly to `/detail/:ticker`. MyPage also lists favorite assets as removable tags and lets authenticated users add favorites from the current market asset list.

As of 2026-06-02, logged-in users also sync favorites to the backend. On login, existing browser-local favorites are imported to `user_favorite_assets`, then localStorage is refreshed from the server response. Anonymous users continue to use browser-local favorites.

## Ownership Map

- Favorite state: `frontend/src/store/favoriteStore.js`
- Favorite toggle and right-side panel: `frontend/src/pages/CategoryView.jsx`
- Detail page favorite toggle: `frontend/src/pages/AssetDetail.jsx`
- Asset display names and ticker fallback: `frontend/src/utils/constants.js`, `frontend/src/utils/formatters.js`
- Backend favorite API: `backend/app/api/favorites.py`
- Backend favorite service/model: `backend/app/services/favorite_service.py`, `backend/app/models.py`

## Data Flow

1. `favoriteStore.js` reads the `favoriteAssets` localStorage key at app startup.
2. Category rows call `toggleFavorite` with `symbol`, display `name`, and `categoryKey`.
3. The detail page can also call `toggleFavorite` for the current ticker.
4. The category favorite panel reads the shared `favorites` array and routes clicks to `/detail/:ticker`.
5. Removing a favorite updates Zustand state and writes the updated array back to localStorage.
6. When authenticated, `App.jsx` calls `syncWithServer(token)` to merge local favorites into the backend account list.
7. Authenticated toggle/remove actions optimistically update localStorage, then call the backend favorite API.

## Contracts

- localStorage key: `favoriteAssets`
- Favorite shape:
  - `symbol`
  - `name`
  - `categoryKey`
- Detail route used by favorites: `/detail/:ticker`

## Change Rules

- Do not store sensitive user data in favorites.
- Account-synced favorites should preserve anonymous localStorage fallback and merge local favorites into the account on login.
- Keep route encoding intact when navigating to tickers such as `KRW=X`, `^GSPC`, or Korean stock codes.

## Verification

- Frontend build from `frontend/`: `npm run build`
- Frontend lint from `frontend/`: `npm run lint`
- Manual browser check: toggle a category row star, reload, click a favorite, and confirm the detail page opens.

## Change Records

- `docs/harness/asset-favorites.md`
- `docs/harness/favorite-asset-notification-implementation-2026-06-02.md`
- `docs/harness/mypage-profile-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-gap-remediation-phase0-1-implementation-2026-06-02.md`

## Open Risks

- Cross-device favorite sync now exists for authenticated users, but anonymous users remain browser-local until they log in and merge local favorites into the account.
