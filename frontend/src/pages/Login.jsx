import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import useAuthStore from "../store/authStore";
import { apiClient } from "../utils/apiClient";

const GOOGLE_SCRIPT_ID = "google-identity-services";
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

const TEXT = {
  title: "로그인",
  subtitle: "Google 계정으로 계속 진행하세요.",
  missingConfig: "Google 로그인 설정이 필요합니다.",
  success: "환영합니다!",
  genericError: "Google 로그인에 실패했습니다.",
  networkError:
    "서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
};

function loadGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }

    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID);
    if (existingScript) {
      existingScript.addEventListener("load", resolve, { once: true });
      existingScript.addEventListener("error", reject, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

export default function Login() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const googleButtonRef = useRef(null);
  const isInitializedRef = useRef(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isGoogleReady, setIsGoogleReady] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function initializeGoogleLogin() {
      if (!GOOGLE_CLIENT_ID) {
        setErrorMessage(TEXT.missingConfig);
        setIsGoogleReady(false);
        return;
      }

      try {
        setErrorMessage("");
        setIsGoogleReady(false);
        await loadGoogleScript();

        if (!isMounted || !googleButtonRef.current) {
          return;
        }

        googleButtonRef.current.innerHTML = "";

        // StrictMode(개발 모드)의 effect 이중 실행으로 initialize()가 중복
        // 호출되면 GSI가 경고를 출력하므로, 초기화는 한 번만 수행한다.
        if (!isInitializedRef.current) {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: async (response) => {
            try {
              setErrorMessage("");

              const authResponse = await apiClient.post("/api/auth/google", {
                credential: response.credential,
              });

              const token = authResponse.data?.access_token;
              const id = authResponse.data?.id;
              const email = authResponse.data?.email;
              const nickname = authResponse.data?.nickname ?? "";

              if (!token) {
                setErrorMessage(TEXT.genericError);
                return;
              }

              login(token, { id, email, nickname });
              toast.success(TEXT.success);
              navigate("/");
            } catch (error) {
              if (!error?.response) {
                setErrorMessage(TEXT.networkError);
                toast.error(TEXT.networkError);
                return;
              }

              const backendMessage =
                error?.response?.data?.detail ||
                error?.response?.data?.message ||
                TEXT.genericError;
              setErrorMessage(String(backendMessage));
            }
            },
          });
          isInitializedRef.current = true;
        }

        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: "filled_black",
          size: "large",
          type: "standard",
          text: "continue_with",
          shape: "rectangular",
          logo_alignment: "left",
          width: 320,
        });

        setIsGoogleReady(true);
      } catch {
        setErrorMessage(TEXT.genericError);
        setIsGoogleReady(false);
      }
    }

    initializeGoogleLogin();

    return () => {
      isMounted = false;
    };
  }, [login, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4">
      <div className="w-full max-w-md rounded-lg border border-slate-700/70 bg-slate-950/80 p-7 shadow-2xl shadow-black/30 sm:p-8">
        <h1 className="text-center text-2xl font-bold text-white">{TEXT.title}</h1>
        <p className="mt-2 text-center text-sm text-slate-400">{TEXT.subtitle}</p>

        <div className="mt-8 flex justify-center">
          <div className="relative flex min-h-11 w-full max-w-[320px] items-center justify-center rounded-lg border border-slate-700/80 bg-black/30 ring-1 ring-white/5">
            {!isGoogleReady && !errorMessage ? (
              <div className="flex h-11 w-full items-center justify-center rounded-lg bg-slate-950 text-sm font-medium text-slate-400">
                로그인 준비 중...
              </div>
            ) : null}
            <div
              ref={googleButtonRef}
              className={isGoogleReady ? "w-full" : "absolute inset-0 overflow-hidden opacity-0"}
            />
          </div>
        </div>

        {errorMessage ? (
          <p className="mt-5 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100 shadow-lg shadow-red-950/20">
            {errorMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}
