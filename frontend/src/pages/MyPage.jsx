import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bell, CheckCircle2, Mail, Search, Star, UserRound } from "lucide-react";

import useAuthStore from "../store/authStore";
import useFavoriteStore from "../store/favoriteStore";
import { apiClient, authHeader } from "../utils/apiClient";
import { ASSET_NAMES, resolveAssetName } from "../utils/constants";
import { formatTicker } from "../utils/formatters";

const defaultPreferences = {
  telegram_enabled: false,
  email_enabled: false,
  price_change_enabled: true,
  news_enabled: true,
  report_enabled: true,
  daily_digest_enabled: false,
  price_change_threshold_percent: 3,
  quiet_hours_start: "",
  quiet_hours_end: "",
  timezone: "Asia/Seoul",
};

const normalizeNickname = (value) => String(value || "").trim().replace(/\s+/g, " ");

const flattenMarketPrices = (payload) => {
  const options = [];
  Object.entries(payload || {}).forEach(([categoryKey, group]) => {
    Object.entries(group || {}).forEach(([label, info]) => {
      const symbol = String(info?.symbol || label || "").trim();
      if (!symbol) return;
      options.push({
        symbol,
        name: resolveAssetName(symbol, label),
        categoryKey,
      });
    });
  });
  return options;
};

const fallbackAssets = Object.entries(ASSET_NAMES).map(([symbol, name]) => ({
  symbol,
  name,
  categoryKey: null,
}));

export default function MyPage() {
  const [searchParams] = useSearchParams();
  const nextPath = searchParams.get("next");
  const { token, user, updateUser } = useAuthStore();
  const { favorites, addFavorite, removeFavorite, syncWithServer, isSyncing, syncError } = useFavoriteStore();

  const headers = useMemo(() => authHeader(token), [token]);
  const [profile, setProfile] = useState(null);
  const [nicknameDraft, setNicknameDraft] = useState(user?.nickname || "");
  const [availabilityStatus, setAvailabilityStatus] = useState("idle");
  const [availabilityMessage, setAvailabilityMessage] = useState("");
  const [lastCheckedNickname, setLastCheckedNickname] = useState("");
  const [preferences, setPreferences] = useState(defaultPreferences);
  const [statusMessage, setStatusMessage] = useState("");
  const [assetOptions, setAssetOptions] = useState(fallbackAssets);
  const [assetQuery, setAssetQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const [profileRes, marketRes] = await Promise.all([
        apiClient.get("/api/profile/me", { headers }),
        apiClient.get("/api/market/prices"),
      ]);
      const nextProfile = profileRes.data;
      setProfile(nextProfile);
      setNicknameDraft(nextProfile.nickname || "");
      setPreferences({ ...defaultPreferences, ...(nextProfile.notification_preferences || {}) });
      updateUser({
        id: nextProfile.id,
        email: nextProfile.email,
        nickname: nextProfile.nickname,
        nickname_confirmed: nextProfile.nickname_confirmed,
        profile_complete: nextProfile.profile_complete,
      });
      setAssetOptions(flattenMarketPrices(marketRes.data));
      await syncWithServer(token);
      setStatusMessage("");
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "마이페이지 정보를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }, [headers, syncWithServer, token, updateUser]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    const normalized = normalizeNickname(nicknameDraft);
    if (normalized !== lastCheckedNickname) {
      setAvailabilityStatus("idle");
      setAvailabilityMessage("");
    }
  }, [lastCheckedNickname, nicknameDraft]);

  const filteredAssets = useMemo(() => {
    const query = assetQuery.trim().toLowerCase();
    if (!query) return assetOptions.slice(0, 8);
    return assetOptions
      .filter((asset) =>
        `${asset.symbol} ${asset.name}`.toLowerCase().includes(query)
      )
      .slice(0, 10);
  }, [assetOptions, assetQuery]);

  const favoriteSymbols = useMemo(
    () => new Set(favorites.map((favorite) => favorite.symbol)),
    [favorites]
  );

  const currentNickname = normalizeNickname(nicknameDraft);
  const canSaveNickname =
    availabilityStatus === "available" &&
    lastCheckedNickname === currentNickname &&
    currentNickname.length > 0;

  const checkNickname = async () => {
    if (!token || !currentNickname) return;
    setAvailabilityStatus("checking");
    try {
      const response = await apiClient.get("/api/profile/nickname-availability", {
        headers,
        params: { nickname: currentNickname },
      });
      setLastCheckedNickname(response.data.nickname);
      setAvailabilityStatus(response.data.available && response.data.valid ? "available" : "unavailable");
      setAvailabilityMessage(response.data.message);
    } catch (error) {
      setAvailabilityStatus("unavailable");
      setAvailabilityMessage(error?.response?.data?.detail || "닉네임 확인에 실패했습니다.");
    }
  };

  const saveNickname = async () => {
    if (!canSaveNickname) return;
    try {
      const response = await apiClient.patch(
        "/api/profile/nickname",
        { nickname: currentNickname },
        { headers }
      );
      const nextUser = response.data;
      updateUser(nextUser);
      setProfile((current) => ({ ...(current || {}), ...nextUser }));
      setStatusMessage("닉네임이 저장되었습니다. 이제 댓글을 작성할 수 있습니다.");
      setAvailabilityStatus("idle");
      setAvailabilityMessage("");
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "닉네임 저장에 실패했습니다.");
    }
  };

  const updatePreference = async (key, value) => {
    const nextPreferences = { ...preferences, [key]: value };
    setPreferences(nextPreferences);
    try {
      const response = await apiClient.put("/api/notifications/preferences", { [key]: value }, { headers });
      setPreferences({ ...defaultPreferences, ...response.data });
      setStatusMessage("수신 동의 설정이 저장되었습니다.");
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "수신 동의 설정 저장에 실패했습니다.");
    }
  };

  if (!token) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-slate-100">마이페이지</h1>
        <p className="mt-4 text-slate-400">프로필과 즐겨찾기 설정은 로그인 후 사용할 수 있습니다.</p>
        <Link to="/login" className="mt-6 inline-flex rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950">
          로그인
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-100">마이페이지</h1>
        <p className="mt-2 text-sm text-slate-400">댓글 프로필, 관심 자산, 알림 수신 동의를 관리합니다.</p>
      </div>

      {statusMessage && (
        <div className="mb-5 rounded-xl border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-200">
          {statusMessage}
        </div>
      )}

      {isLoading && (
        <div className="mb-5 rounded-xl border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-400">
          마이페이지 정보를 불러오는 중입니다...
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
          <div className="mb-4 flex items-center gap-2">
            <UserRound size={20} className="text-emerald-400" />
            <h2 className="text-lg font-bold text-slate-100">프로필</h2>
          </div>
          <div className="space-y-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Google 계정</div>
              <div className="mt-1 text-sm text-slate-200">{profile?.email || user?.email}</div>
            </div>

            <label className="block text-sm text-slate-200">
              닉네임
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <input
                  value={nicknameDraft}
                  onChange={(event) => setNicknameDraft(event.target.value)}
                  maxLength={40}
                  className="min-w-0 flex-1 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <button
                  type="button"
                  onClick={checkNickname}
                  disabled={availabilityStatus === "checking"}
                  className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  중복 확인
                </button>
                <button
                  type="button"
                  onClick={saveNickname}
                  disabled={!canSaveNickname}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  저장
                </button>
              </div>
            </label>

            <div className="min-h-6 text-sm">
              {availabilityStatus === "available" && (
                <span className="inline-flex items-center gap-1 text-emerald-300">
                  <CheckCircle2 size={16} />
                  {availabilityMessage}
                </span>
              )}
              {availabilityStatus === "unavailable" && <span className="text-amber-300">{availabilityMessage}</span>}
              {availabilityStatus === "checking" && <span className="text-slate-400">확인 중입니다...</span>}
              {profile?.nickname_confirmed ? (
                <p className="mt-2 text-xs text-slate-500">댓글 작성 프로필이 설정되어 있습니다.</p>
              ) : (
                <p className="mt-2 text-xs text-amber-200">닉네임을 저장해야 댓글을 작성할 수 있습니다.</p>
              )}
            </div>

            {nextPath && (
              <Link
                to={nextPath}
                className="inline-flex rounded-lg border border-emerald-400/50 px-4 py-2 text-sm font-semibold text-emerald-200 hover:bg-emerald-400/10"
              >
                이전 화면으로 돌아가기
              </Link>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
          <div className="mb-4 flex items-center gap-2">
            <Bell size={20} className="text-cyan-300" />
            <h2 className="text-lg font-bold text-slate-100">수신 동의</h2>
          </div>
          <p className="mb-4 text-sm leading-6 text-slate-400">
            체크를 해제하면 해당 채널의 알림 수신만 중지됩니다. 연결된 이메일이나 Telegram 정보는 유지됩니다.
          </p>
          <div className="space-y-3">
            <label className="flex items-center justify-between rounded-lg bg-slate-900/40 px-4 py-3 text-sm text-slate-200">
              <span className="inline-flex items-center gap-2">
                <Bell size={16} className="text-cyan-300" />
                Telegram 수신
              </span>
              <input
                type="checkbox"
                checked={Boolean(preferences.telegram_enabled)}
                onChange={(event) => updatePreference("telegram_enabled", event.target.checked)}
                className="h-5 w-5 accent-emerald-500"
              />
            </label>
            <label className="flex items-center justify-between rounded-lg bg-slate-900/40 px-4 py-3 text-sm text-slate-200">
              <span className="inline-flex items-center gap-2">
                <Mail size={16} className="text-amber-300" />
                Google Mail 수신
              </span>
              <input
                type="checkbox"
                checked={Boolean(preferences.email_enabled)}
                onChange={(event) => updatePreference("email_enabled", event.target.checked)}
                className="h-5 w-5 accent-emerald-500"
              />
            </label>
          </div>
        </section>
      </div>

      <section className="mt-5 rounded-xl border border-slate-700 bg-slate-800/70 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Star size={20} className="text-amber-300" fill="currentColor" />
            <h2 className="text-lg font-bold text-slate-100">즐겨찾기 자산</h2>
          </div>
          {isSyncing && <span className="text-xs text-slate-500">계정 즐겨찾기 동기화 중...</span>}
        </div>
        {syncError && <p className="mb-3 text-sm text-amber-300">{syncError}</p>}

        <div className="mb-5 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
          <Search size={17} className="text-slate-500" />
          <input
            value={assetQuery}
            onChange={(event) => setAssetQuery(event.target.value)}
            placeholder="티커나 자산명으로 검색"
            className="min-w-0 flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
        </div>

        <div className="mb-5 grid gap-2 md:grid-cols-2">
          {filteredAssets.map((asset) => {
            const alreadyFavorite = favoriteSymbols.has(asset.symbol);
            return (
              <div key={`${asset.categoryKey || "asset"}-${asset.symbol}`} className="flex items-center gap-3 rounded-lg bg-slate-900/45 p-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-slate-100">{asset.name}</div>
                  <div className="text-xs text-slate-500">{formatTicker(asset.symbol)}</div>
                </div>
                <button
                  type="button"
                  onClick={() => addFavorite(asset)}
                  disabled={alreadyFavorite}
                  className="rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  {alreadyFavorite ? "추가됨" : "추가"}
                </button>
              </div>
            );
          })}
        </div>

        {favorites.length === 0 ? (
          <div className="rounded-lg bg-slate-900/35 px-4 py-6 text-center text-sm text-slate-400">
            아직 즐겨찾기 자산이 없습니다.
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {favorites.map((favorite) => (
              <span
                key={favorite.symbol}
                className="inline-flex items-center gap-2 rounded-full border border-slate-600 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
              >
                <Link to={`/detail/${encodeURIComponent(favorite.symbol)}`} className="hover:text-emerald-300">
                  {resolveAssetName(favorite.symbol, favorite.name)}
                </Link>
                <button
                  type="button"
                  onClick={() => removeFavorite(favorite.symbol)}
                  className="text-slate-500 hover:text-red-300"
                  aria-label={`${favorite.symbol} 즐겨찾기 해제`}
                >
                  x
                </button>
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
