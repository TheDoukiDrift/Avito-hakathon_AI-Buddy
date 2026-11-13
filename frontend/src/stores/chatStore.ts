import { create } from 'zustand'
import * as api from '../api/client'
import type { ChatMessage } from '../api/schemas'

const FALLBACK_ANSWER = 'Не удалось получить ответ. Попробуйте ещё раз.'
const EMPTY_ANSWER = 'Бадди не ответил. Попробуйте переформулировать вопрос.'

let localCounter = 0

function nextLocalId(): string {
  localCounter += 1
  return `local-${localCounter}`
}

function nowIso(): string {
  return new Date().toISOString()
}

interface ChatState {
  messages: ChatMessage[]
  historyLoaded: boolean
  loadingHistory: boolean
  sending: boolean
  error: string | null
  loadHistory: () => Promise<void>
  sendMessage: (text: string) => Promise<void>
  reset: () => void
}

function errorText(error: unknown): string {
  if (error instanceof api.ApiError) return error.message
  if (error instanceof Error) return error.message
  return FALLBACK_ANSWER
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  historyLoaded: false,
  loadingHistory: false,
  sending: false,
  error: null,

  async loadHistory() {
    if (get().historyLoaded || get().loadingHistory) return
    set({ loadingHistory: true, error: null })
    try {
      const history = await api.fetchChatHistory()
      set((state) => ({
        // Отправка могла начаться раньше ответа истории: локальные сообщения
        // не теряем, историю кладём перед ними.
        messages: state.messages.length > 0 ? [...history, ...state.messages] : history,
        historyLoaded: true,
        loadingHistory: false,
      }))
    } catch (error) {
      set({ loadingHistory: false, error: errorText(error) })
    }
  },

  async sendMessage(text) {
    const trimmed = text.trim()
    if (!trimmed || get().sending) return

    const assistantId = nextLocalId()
    const userMessage: ChatMessage = {
      id: nextLocalId(),
      role: 'user',
      content: trimmed,
      created_at: nowIso(),
    }
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      created_at: nowIso(),
    }

    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
      sending: true,
      error: null,
    }))

    const patchAssistant = (patch: (content: string) => string) => {
      set((state) => ({
        messages: state.messages.map((message) =>
          message.id === assistantId ? { ...message, content: patch(message.content) } : message,
        ),
      }))
    }

    try {
      await api.streamChat(trimmed, (token) => patchAssistant((content) => content + token))
      set((state) => ({
        sending: false,
        messages: state.messages.map((message) =>
          message.id === assistantId && message.content.trim() === ''
            ? { ...message, content: EMPTY_ANSWER }
            : message,
        ),
      }))
    } catch (error) {
      // Частичный ответ сохраняем как есть: строка ошибки живёт отдельно,
      // текст бадди не затираем и не дописываем в тело сообщения.
      patchAssistant((content) => (content.trim() === '' ? FALLBACK_ANSWER : content))
      set({ sending: false, error: errorText(error) })
    }
  },

  reset() {
    set({
      messages: [],
      historyLoaded: false,
      loadingHistory: false,
      sending: false,
      error: null,
    })
  },
}))
