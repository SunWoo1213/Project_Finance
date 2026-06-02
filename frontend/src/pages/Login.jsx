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
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function initializeGoogleLogin() {
      if (!GOOGLE_CLIENT_ID) {
        setErrorMessage(TEXT.missingConfig);
        return;
      }

      try {
        await loadGoogleScript();

        if (!isMounted || !googleButtonRef.current) {
          return;
        }

        googleButtonRef.current.innerHTML = "";

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

        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: "outline",
          size: "large",
          type: "standard",
          text: "continue_with",
          shape: "rectangular",
          width: 320,
        });
      } catch {
        setErrorMessage(TEXT.genericError);
      }
    }

    initializeGoogleLogin();

    return () => {
      isMounted = false;
    };
  }, [login, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-7 shadow-xl sm:p-8">
        <h1 className="text-center text-2xl font-bold text-white">{TEXT.title}</h1>
        <p className="mt-2 text-center text-sm text-slate-400">{TEXT.subtitle}</p>

        <div className="mt-8 flex justify-center">
          <div ref={googleButtonRef} />
        </div>

        {errorMessage ? (
          <p className="mt-5 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {errorMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}
