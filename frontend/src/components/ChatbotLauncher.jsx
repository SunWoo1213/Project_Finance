import { Bot, MessageCircle } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import useAuthStore from "../store/authStore";
import useChatStore from "../store/chatStore";
import { buildChatContext } from "../utils/chatContext";
import ChatbotPanel from "./ChatbotPanel";

export default function ChatbotLauncher() {
  const location = useLocation();
  const navigate = useNavigate();
  const authState = useAuthStore();
  const { isOpen, open, close, toggle } = useChatStore();
  const chatContext = buildChatContext({ location, authState });

  const handleAction = (action) => {
    if (!action?.url) return;
    navigate(action.url);
    close();
  };

  return (
    <>
      {isOpen && (
        <ChatbotPanel
          chatContext={chatContext}
          token={authState.token}
          onClose={close}
          onAction={handleAction}
        />
      )}
      <button
        type="button"
        onClick={isOpen ? toggle : open}
        className="fixed bottom-5 right-5 z-50 inline-flex h-14 w-14 items-center justify-center rounded-full border border-emerald-300/50 bg-emerald-500 text-slate-950 shadow-xl shadow-black/30 transition-transform hover:scale-105 hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-200"
        aria-label={isOpen ? "챗봇 닫기" : "챗봇 열기"}
        title={isOpen ? "챗봇 닫기" : "챗봇 열기"}
      >
        {isOpen ? <Bot size={24} /> : <MessageCircle size={25} />}
      </button>
    </>
  );
}
