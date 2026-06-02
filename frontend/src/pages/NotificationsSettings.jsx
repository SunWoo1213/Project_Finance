import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, Mail, Send, Smartphone } from "lucide-react";

import useAuthStore from "../store/authStore";
import { apiClient, authHeader } from "../utils/apiClient";

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

export default function NotificationsSettings() {
  const { token, user } = useAuthStore();
  const [preferences, setPreferences] = useState(defaultPreferences);
  const [channels, setChannels] = useState([]);
  const [history, setHistory] = useState([]);
  const [telegramCode, setTelegramCode] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailAddress, setEmailAddress] = useState(user?.email || "");
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const headers = useMemo(() => authHeader(token), [token]);

  const loadSettings = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const [preferenceRes, channelRes, historyRes] = await Promise.all([
        apiClient.get("/api/notifications/preferences", { headers }),
        apiClient.get("/api/notifications/channels", { headers }),
        apiClient.get("/api/notifications/history?limit=20", { headers }),
      ]);
      setPreferences({ ...defaultPreferences, ...preferenceRes.data });
      setChannels(channelRes.data);
      setHistory(historyRes.data);
      setStatusMessage("");
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "알림 설정을 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }, [headers, token]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const savePreferences = async (nextPreferences = preferences) => {
    if (!token) return;
    try {
      const response = await apiClient.put("/api/notifications/preferences", nextPreferences, { headers });
      setPreferences({ ...defaultPreferences, ...response.data });
      setStatusMessage("알림 설정을 저장했습니다.");
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "알림 설정 저장에 실패했습니다.");
    }
  };

  const updateToggle = (key) => {
    const next = { ...preferences, [key]: !preferences[key] };
    setPreferences(next);
    savePreferences(next);
  };

  const requestTelegramCode = async () => {
    try {
      const response = await apiClient.post("/api/notifications/channels/telegram/connect", {}, { headers });
      setTelegramCode(response.data.verification_code);
      setStatusMessage("Telegram 연결 코드가 발급되었습니다.");
      await loadSettings();
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
      await loadSettings();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "Telegram 검증에 실패했습니다.");
    }
  };

  const requestEmailCode = async () => {
    try {
      const response = await apiClient.post(
        "/api/notifications/channels/email/verify",
        { email: emailAddress || user?.email },
        { headers }
      );
      setEmailCode("");
      setStatusMessage(response.data.message || "Gmail로 확인 코드를 보냈습니다.");
      await loadSettings();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "Gmail 확인 코드를 보내지 못했습니다.");
    }
  };

  const confirmEmail = async () => {
    try {
      await apiClient.post(
        "/api/notifications/channels/email/confirm",
        { code: emailCode, email: emailAddress || user?.email },
        { headers }
      );
      setStatusMessage("이메일 채널을 연결했습니다.");
      await loadSettings();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "이메일 검증에 실패했습니다.");
    }
  };

  const sendTest = async () => {
    try {
      const response = await apiClient.post(
        "/api/notifications/test",
        { ticker: "TEST", message: "테스트 알림입니다." },
        { headers }
      );
      setStatusMessage(response.data.message);
      await loadSettings();
    } catch (error) {
      setStatusMessage(error?.response?.data?.detail || "테스트 알림 처리에 실패했습니다.");
    }
  };

  const getChannel = (name) => channels.find((channel) => channel.channel === name);

  if (!token) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-slate-100">알림 설정</h1>
        <p className="mt-4 text-slate-400">즐겨찾기 자산 알림은 로그인 후 사용할 수 있습니다.</p>
        <Link to="/login" className="mt-6 inline-flex rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950">
          로그인
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <Bell className="text-emerald-400" size={26} />
        <div>
          <h1 className="text-2xl font-bold text-slate-100">즐겨찾기 자산 알림</h1>
          <p className="mt-1 text-sm text-slate-400">가격 변동, 새 뉴스, 저장된 AI 리포트 갱신을 계정 기준으로 추적합니다.</p>
        </div>
      </div>

      {statusMessage && (
        <div className="mb-5 rounded-xl border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-200">
          {statusMessage}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
          <h2 className="mb-4 text-lg font-bold text-slate-100">알림 조건</h2>
          <div className="space-y-4">
            {[
              ["price_change_enabled", "가격 변동 알림"],
              ["news_enabled", "새 뉴스 알림"],
              ["report_enabled", "AI 리포트 갱신 알림"],
              ["daily_digest_enabled", "일일 요약"],
            ].map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-3 text-sm text-slate-200">
                <span>{label}</span>
                <input
                  type="checkbox"
                  checked={Boolean(preferences[key])}
                  onChange={() => updateToggle(key)}
                  className="h-5 w-5 accent-emerald-500"
                />
              </label>
            ))}

            <label className="block text-sm text-slate-200">
              가격 변동 기준
              <div className="mt-2 flex items-center gap-3">
                <input
                  type="number"
                  min="0.1"
                  max="50"
                  step="0.1"
                  value={preferences.price_change_threshold_percent}
                  onChange={(event) =>
                    setPreferences({
                      ...preferences,
                      price_change_threshold_percent: Number(event.target.value),
                    })
                  }
                  onBlur={() => savePreferences()}
                  className="w-28 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100"
                />
                <span className="text-slate-400">% 이상</span>
              </div>
            </label>
          </div>
        </section>

        <section className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
          <h2 className="mb-4 text-lg font-bold text-slate-100">채널 연결</h2>
          <div className="space-y-5">
            <div className="rounded-lg bg-slate-900/45 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 font-semibold text-slate-100">
                  <Smartphone size={18} className="text-cyan-300" />
                  Telegram
                </div>
                <span className="text-xs text-slate-400">
                  {getChannel("telegram")?.verified ? "연결됨" : "미연결"}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={requestTelegramCode} className="rounded-md bg-slate-700 px-3 py-2 text-sm">
                  코드 발급
                </button>
                <input
                  value={telegramCode}
                  onChange={(event) => setTelegramCode(event.target.value)}
                  placeholder="연결 코드"
                  className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm"
                />
                <input
                  value={telegramChatId}
                  onChange={(event) => setTelegramChatId(event.target.value)}
                  placeholder="chat_id"
                  className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm"
                />
                <button type="button" onClick={verifyTelegram} className="rounded-md bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950">
                  확인
                </button>
              </div>
            </div>

            <div className="rounded-lg bg-slate-900/45 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 font-semibold text-slate-100">
                  <Mail size={18} className="text-amber-300" />
                  Email
                </div>
                <span className="text-xs text-slate-400">
                  {getChannel("email")?.verified ? "연결됨" : "미연결"}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  value={emailAddress}
                  onChange={(event) => setEmailAddress(event.target.value)}
                  placeholder={user?.email || "email@example.com"}
                  className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm"
                />
                <button type="button" onClick={requestEmailCode} className="rounded-md bg-slate-700 px-3 py-2 text-sm">
                  코드 발급
                </button>
                <input
                  value={emailCode}
                  onChange={(event) => setEmailCode(event.target.value)}
                  placeholder="Gmail 확인 코드"
                  className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm"
                />
                <button type="button" onClick={confirmEmail} className="rounded-md bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950">
                  확인
                </button>
              </div>
            </div>

            <button
              type="button"
              onClick={sendTest}
              className="inline-flex items-center gap-2 rounded-lg bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950"
            >
              <Send size={16} />
              테스트 알림
            </button>
          </div>
        </section>
      </div>

      <section className="mt-6 rounded-xl border border-slate-700 bg-slate-800/70 p-5">
        <h2 className="mb-4 text-lg font-bold text-slate-100">최근 알림 이력</h2>
        {isLoading ? (
          <div className="py-8 text-center text-slate-400">불러오는 중입니다...</div>
        ) : history.length === 0 ? (
          <div className="py-8 text-center text-slate-400">아직 알림 이력이 없습니다.</div>
        ) : (
          <div className="space-y-3">
            {history.map((event) => (
              <div key={event.id} className="rounded-lg border border-slate-700/70 bg-slate-900/35 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-semibold text-slate-100">{event.title}</div>
                  <div className="text-xs text-slate-500">
                    {event.channel} · {event.status}
                  </div>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{event.body}</p>
                {event.error_message && <p className="mt-2 text-xs text-red-300">{event.error_message}</p>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
