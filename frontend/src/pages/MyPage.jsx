import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bell, CheckCircle2, Mail, Search, Smartphone, Star, UserRound } from "lucide-react";

import useAuthStore from "../store/authStore";
import useFavoriteStore from "../store/favoriteStore";
import useSubscriptionStore from "../store/subscriptionStore";
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

const maskDestination = (channel, value) => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (channel === "email") {
    const [local, domain] = raw.split("@");
    if (!domain) return `${raw.slice(0, 2)}***`;
    const head = local.slice(0, 2);
    return `${head}${"*".repeat(Math.max(local.length - 2, 1))}@${domain}`;
  }
  // telegram chat_id 등 숫자/문자 식별자는 앞 2자리만 노출
  if (raw.length <= 3) return `${raw.slice(0, 1)}***`;
  return `${raw.slice(0, 2)}***${raw.slice(-2)}`;
};

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

const telegramManualHelp =
  "Telegram bot과 먼저 대화를 시작한 뒤, 숫자 chat_id와 발급된 연결 코드를 함께 입력해 검증합니다.";

export default function MyPage() {
  const [searchParams] = useSearchParams();
  const nextPath = searchParams.get("next");
  const { token, user, updateUser } = useAuthStore();
  const { favorites, addFavorite, removeFavorite, syncWithServer, isSyncing, syncError } = useFavoriteStore();
  const canUseNotifications = useSubscriptionStore(
    (state) => state.entitlements.can_use_notifications
  );

  const headers = useMemo(() => authHeader(token), [token]);
  const [profile, setProfile] = useState(null);
  const [nicknameDraft, setNicknameDraft] = useState(user?.nickname || "");
  const [availabilityStatus, setAvailabilityStatus] = useState("idle");
  const [availabilityMessage, setAvailabilityMessage] = useState("");
  const [lastCheckedNickname, setLastCheckedNickname] = useState("");
  const [preferences, setPreferences] = useState(defaultPreferences);
  const [channels, setChannels] = useState([]);
  const [telegramCode, setTelegramCode] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailAddress, setEmailAddress] = useState(user?.email || "");
  const [statusMessage, setStatusMessage] = useState("");
  const [assetOptions, setAssetOptions] = useState(fallbackAssets);
  const [assetQuery, setAssetQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const [profileRes, marketRes, channelRes] = await Promise.all([
        apiClient.get("/api/profile/me", { headers }),
        apiClient.get("/api/market/prices"),
        // 채널 조회 실패가 프로필 로딩 전체를 막지 않도록 개별 fallback 처리
        apiClient.get("/api/notifications/channels", { headers }).catch(() => ({ data: [] })),
      ]);
      const nextProfile = profileRes.data;
      setProfile(nextProfile);
      setNicknameDraft(nextProfile.nickname || "");
      setPreferences({ ...defaultPreferences, ...(nextProfile.notification_preferences || {}) });
      setChannels(Array.isArray(channelRes.data) ? channelRes.data : []);
      setEmailAddress((current) => current || nextProfile.email || "");
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

  const reloadChannels = useCallback(async () => {
    try {
      const response = await apiClient.get("/api/notifications/channels", { headers });
      setChannels(Array.isArray(response.data) ? response.data : []);
    } catch {
      // 채널 재조회 실패는 화면 전체에 영향을 주지 않으므로 무시한다.
    }
  }, [headers]);

  const getChannel = (name) => channels.find((channel) => channel.channel === name);

  const requestTelegramCode = async () => {
    try {
      const response = await apiClient.post("/api/notifications/channels/telegram/connect", {}, { headers });
      setTelegramCode(response.data.verification_code || "");
      setStatusMessage(response.data.message || telegramManualHelp);
      setStatusMessage("Telegram 연결 코드가 발급되었습니다. 봇과 대화 후 코드를 전송하세요.");
      setStatusMessage(response.data.message || telegramManualHelp);
      await reloadChannels();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "Telegram 연결 코드를 만들지 못했습니다.");
    }
  };

  const verifyTelegram = async () => {
    try {
      await apiClient.post(
        "/api/notifications/channels/telegram/verify",
        { code: telegramCode, chat_id: telegramChatId },
        { headers }
      );
      setStatusMessage("Telegram 채널을 연결했습니다.");
      setTelegramCode("");
      setTelegramChatId("");
      await reloadChannels();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "Telegram 검증에 실패했습니다.");
    }
  };

  const disconnectTelegram = async () => {
    try {
      await apiClient.delete("/api/notifications/channels/telegram", { headers });
      setStatusMessage("Telegram 채널 연결을 해제했습니다.");
      await reloadChannels();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "Telegram 연결 해제에 실패했습니다.");
    }
  };

  const requestEmailCode = async () => {
    try {
      const response = await apiClient.post(
        "/api/notifications/channels/email/verify",
        { email: emailAddress || profile?.email },
        { headers }
      );
      setEmailCode("");
      setStatusMessage(response.data.message || "Gmail로 확인 코드를 보냈습니다.");
      await reloadChannels();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "Gmail 확인 코드를 보내지 못했습니다.");
    }
  };

  const confirmEmail = async () => {
    try {
      await apiClient.post(
        "/api/notifications/channels/email/confirm",
        { code: emailCode, email: emailAddress || profile?.email },
        { headers }
      );
      setStatusMessage("이메일 채널을 연결했습니다.");
      setEmailCode("");
      await reloadChannels();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "이메일 검증에 실패했습니다.");
    }
  };

  const disconnectEmail = async () => {
    try {
      await apiClient.delete("/api/notifications/channels/email", { headers });
      setStatusMessage("이메일 채널 연결을 해제했습니다.");
      await reloadChannels();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "이메일 연결 해제에 실패했습니다.");
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
          {!canUseNotifications && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
              <span className="text-amber-200">
                이메일·Telegram 외부 발송 알림은 <span className="font-semibold">PLUS 이상</span>에서 사용할 수 있습니다. 앱 내 알림은 모든 등급에서 제공됩니다.
              </span>
              <Link
                to="/pricing"
                className="rounded-md bg-amber-500 px-3 py-1.5 text-xs font-bold text-slate-950 hover:bg-amber-400"
              >
                플랜 업그레이드
              </Link>
            </div>
          )}
          <div className="space-y-4">
            <div className="rounded-lg bg-slate-900/40 p-4">
              <label className="flex items-center justify-between text-sm text-slate-200">
                <span className="inline-flex items-center gap-2">
                  <Smartphone size={16} className="text-cyan-300" />
                  Telegram 수신
                </span>
                <input
                  type="checkbox"
                  checked={Boolean(preferences.telegram_enabled)}
                  onChange={(event) => updatePreference("telegram_enabled", event.target.checked)}
                  disabled={!canUseNotifications}
                  className="h-5 w-5 accent-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </label>

              {!canUseNotifications ? (
                <p className="mt-3 text-xs leading-5 text-slate-500">
                  PLUS 이상 구독 시 Telegram 채널을 연결하고 외부 알림을 받을 수 있습니다.
                </p>
              ) : getChannel("telegram")?.verified ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-950/60 px-3 py-2 text-xs">
                  <span className="inline-flex items-center gap-1 text-emerald-300">
                    <CheckCircle2 size={14} />
                    연결됨 · chat_id {maskDestination("telegram", getChannel("telegram")?.destination)}
                  </span>
                  <button
                    type="button"
                    onClick={disconnectTelegram}
                    className="rounded-md border border-slate-600 px-2.5 py-1 text-slate-300 hover:border-red-400 hover:text-red-300"
                  >
                    해제
                  </button>
                </div>
              ) : (
                <div className="mt-3 space-y-2">
                  <p className="text-xs leading-5 text-slate-400">
                    봇과 1회 대화한 뒤 받은 <span className="text-slate-200">숫자 chat_id</span>를 입력하세요. 먼저 코드를 발급받아 봇에게 전송한 후 검증합니다.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={requestTelegramCode}
                      className="rounded-md bg-slate-700 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-600"
                    >
                      코드 발급
                    </button>
                    <input
                      value={telegramCode}
                      onChange={(event) => setTelegramCode(event.target.value)}
                      placeholder="연결 코드"
                      className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100"
                    />
                    <input
                      value={telegramChatId}
                      onChange={(event) => setTelegramChatId(event.target.value)}
                      placeholder="숫자 chat_id"
                      inputMode="numeric"
                      className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100"
                    />
                    <button
                      type="button"
                      onClick={verifyTelegram}
                      disabled={!telegramCode || !telegramChatId}
                      className="rounded-md bg-emerald-500 px-3 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      확인
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="rounded-lg bg-slate-900/40 p-4">
              <label className="flex items-center justify-between text-sm text-slate-200">
                <span className="inline-flex items-center gap-2">
                  <Mail size={16} className="text-amber-300" />
                  Google Mail 수신
                </span>
                <input
                  type="checkbox"
                  checked={Boolean(preferences.email_enabled)}
                  onChange={(event) => updatePreference("email_enabled", event.target.checked)}
                  disabled={!canUseNotifications}
                  className="h-5 w-5 accent-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </label>

              {!canUseNotifications ? (
                <p className="mt-3 text-xs leading-5 text-slate-500">
                  PLUS 이상 구독 시 Google Mail 채널을 연결하고 외부 알림을 받을 수 있습니다.
                </p>
              ) : getChannel("email")?.verified ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-950/60 px-3 py-2 text-xs">
                  <span className="inline-flex items-center gap-1 text-emerald-300">
                    <CheckCircle2 size={14} />
                    연결됨 · {maskDestination("email", getChannel("email")?.destination)}
                  </span>
                  <button
                    type="button"
                    onClick={disconnectEmail}
                    className="rounded-md border border-slate-600 px-2.5 py-1 text-slate-300 hover:border-red-400 hover:text-red-300"
                  >
                    해제
                  </button>
                </div>
              ) : (
                <div className="mt-3 space-y-2">
                  <p className="text-xs leading-5 text-slate-400">
                    수신 이메일로 확인 코드가 Gmail을 통해 발송됩니다. 받은 코드를 입력해 검증하세요.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <input
                      value={emailAddress}
                      onChange={(event) => setEmailAddress(event.target.value)}
                      placeholder={profile?.email || "email@example.com"}
                      className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100"
                    />
                    <button
                      type="button"
                      onClick={requestEmailCode}
                      className="rounded-md bg-slate-700 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-600"
                    >
                      코드 발급
                    </button>
                    <input
                      value={emailCode}
                      onChange={(event) => setEmailCode(event.target.value)}
                      placeholder="Gmail 확인 코드"
                      className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100"
                    />
                    <button
                      type="button"
                      onClick={confirmEmail}
                      disabled={!emailCode}
                      className="rounded-md bg-emerald-500 px-3 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      확인
                    </button>
                  </div>
                </div>
              )}
            </div>
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
