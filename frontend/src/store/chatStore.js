import { create } from "zustand";

import { apiClient, authHeader } from "../utils/apiClient";

const createId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const initialAssistantMessage = {
  id: "welcome",
  role: "assistant",
  content: "무엇을 도와드릴까요? 자산, 리포트, 뉴스, 댓글 기능을 물어보세요.",
  actions: [],
  cards: [],
};

const useChatStore = create((set, get) => ({
  isOpen: false,
  messages: [initialAssistantMessage],
  isSending: false,
  error: null,
  conversationId: createId(),
  lastRequest: null,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  clear: () =>
    set({
      messages: [initialAssistantMessage],
      error: null,
      conversationId: createId(),
      lastRequest: null,
    }),
  sendMessage: async (text, chatContext, token) => {
    const trimmed = text.trim();
    if (!trimmed || get().isSending) return;

    const userMessage = {
      id: createId(),
      role: "user",
      content: trimmed,
    };

    // Send recent turns so the backend LLM path can use conversation context.
    // The server does not persist these; they are prompt context only.
    const history = get()
      .messages.filter((m) => m.id !== "welcome" && (m.role === "user" || m.role === "assistant"))
      .slice(-12)
      .map((m) => ({ role: m.role, content: m.content }));

    set((state) => ({
      messages: [...state.messages, userMessage],
      isSending: true,
      error: null,
      lastRequest: { text: trimmed, chatContext, token },
    }));

    try {
      const { data } = await apiClient.post(
        "/api/chat/message",
        {
          message: trimmed,
          current_path: chatContext.current_path,
          context: chatContext.context,
          conversation_id: get().conversationId,
          client_message_id: userMessage.id,
          history,
        },
        { headers: authHeader(token) }
      );

      const assistantMessage = {
        id: createId(),
        role: "assistant",
        content: data.answer,
        intent: data.intent,
        actions: data.actions || [],
        cards: data.cards || [],
        disclaimer: data.disclaimer,
        requiresAuth: data.requires_auth,
      };

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isSending: false,
        error: null,
      }));
    } catch (error) {
      set({
        isSending: false,
        error: error?.response?.data?.detail || "응답을 불러오지 못했습니다. 다시 시도해주세요.",
      });
    }
  },
  retryLast: async () => {
    const request = get().lastRequest;
    if (!request) return;
    await get().sendMessage(request.text, request.chatContext, request.token);
  },
}));

export default useChatStore;
