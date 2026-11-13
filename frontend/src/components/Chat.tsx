import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useChatStore } from '../stores/chatStore'
import { InlineError } from './InlineError'
import { LoadingLine } from './LoadingLine'
import { Message } from './Message'

const SUGGESTIONS = [
  'Как оформить отгул?',
  'Что в моём чек-листе?',
  'К кому обратиться по поводу командировки?',
]

export function Chat() {
  const messages = useChatStore((state) => state.messages)
  const historyLoaded = useChatStore((state) => state.historyLoaded)
  const sending = useChatStore((state) => state.sending)
  const loadingHistory = useChatStore((state) => state.loadingHistory)
  const error = useChatStore((state) => state.error)
  const loadHistory = useChatStore((state) => state.loadHistory)
  const sendMessage = useChatStore((state) => state.sendMessage)

  const [draft, setDraft] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  // Прокрутка мгновенная: во время стрима плавный скролл отстаёт от текста.
  useEffect(() => {
    const node = scrollRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [messages, sending, error])

  const submit = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    void sendMessage(text)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const sendSuggestion = (text: string) => {
    if (sending) return
    void sendMessage(text)
  }

  const lastUserMessage = messages.reduce<string | null>(
    (acc, message) => (message.role === 'user' ? message.content : acc),
    null,
  )

  // Повтор после обрыва: сначала пробуем догрузить историю, иначе повторяем
  // последний вопрос — частичный ответ остаётся на месте.
  const retry = () => {
    if (!historyLoaded) {
      void loadHistory()
      return
    }
    if (lastUserMessage && !sending) void sendMessage(lastUserMessage)
  }

  return (
    <section className="chat" aria-label="Чат с бадди">
      <div className="chat__head">
        <div className="sec-head">
          <span className="sec-num">01 —</span>
          <h2 className="sec-title">Чат</h2>
          <span className="sec-rule" />
          {sending ? (
            <span className="badge badge--wait">Ожидание ответа</span>
          ) : (
            <span className="badge badge--live">На связи</span>
          )}
        </div>
        <p className="chat__subtitle">Бадди отвечает о процессах, инструментах и адаптации</p>
      </div>

      <div className="chat__messages" aria-live="polite" ref={scrollRef}>
        {loadingHistory && messages.length === 0 ? (
          <div className="chat__placeholder">
            <LoadingLine label="Загружаем историю" />
          </div>
        ) : null}

        {!loadingHistory && !error && messages.length === 0 ? (
          <div className="chat__empty">
            <p className="chat__empty-title">Привет! Я бадди — помогу освоиться.</p>
            <p className="chat__empty-text">
              Спросите о процедурах, чек-листе или организационных действиях. Можно начать
              с одного из вопросов:
            </p>
            <div className="chat__suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="button button--ghost"
                  onClick={() => sendSuggestion(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((message, index) => (
          <Message
            key={message.id}
            message={message}
            streaming={sending && index === messages.length - 1 && message.role === 'assistant'}
          />
        ))}
      </div>

      {error ? <InlineError message={error} onRetry={retry} /> : null}

      <form className="chat__composer" onSubmit={submit}>
        <textarea
          className="chat__input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Спросите что-нибудь у бадди…"
          rows={1}
          aria-label="Сообщение"
        />
        <button
          className="button button--primary chat__send"
          type="submit"
          disabled={sending || draft.trim().length === 0}
        >
          {sending ? 'Печатает…' : 'Отправить'}
        </button>
      </form>
      <p className="chat__hint">Enter — отправить, Shift + Enter — новая строка</p>
    </section>
  )
}
