import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useChatStore } from '../stores/chatStore'
import { Icon } from './Icon'
import { InlineError } from './InlineError'
import { LoadingLine } from './LoadingLine'
import { Message } from './Message'
import { ChatMark } from './Rings'

const SUGGESTIONS = [
  'Как оформить отгул?',
  'Что в моём чек-листе?',
  'К кому обратиться по поводу командировки?',
]

interface ChatProps {
  /** На узких экранах чат — выдвижная панель; на широких проп не нужен. */
  open?: boolean
  onClose?: () => void
}

export function Chat({ open = false, onClose }: ChatProps) {
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
    <aside className={`chat ${open ? 'chat--open' : ''}`.trim()} aria-label="Чат с бадди">
      <div className="chat__head">
        <ChatMark />
        <div className="chat__title">
          <strong>AI-buddy</strong>
          <small>Помощник по адаптации · {sending ? 'готовит ответ' : 'на связи'}</small>
        </div>
        {onClose ? (
          <button className="chat__close" type="button" onClick={onClose} aria-label="Закрыть чат">
            <Icon name="x" size={20} />
          </button>
        ) : null}
      </div>

      <div className="scope">
        <Icon name="shield" size={16} /> Отвечаю в рамках твоего доступа
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
              Спроси о процедурах, чек-листе или организационных действиях. Можно начать с
              одного из вопросов:
            </p>
            <div className="hints">
              {SUGGESTIONS.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => sendSuggestion(suggestion)}>
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

      <div className="chat__foot">
        <form className="compose" onSubmit={submit}>
          <textarea
            className="chat__input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Спроси что-нибудь у бадди…"
            rows={1}
            aria-label="Сообщение"
          />
          <button
            className="compose__send"
            type="submit"
            disabled={sending || draft.trim().length === 0}
            aria-label={sending ? 'Печатает…' : 'Отправить'}
          >
            <Icon name="send" size={19} />
          </button>
        </form>
        <p className="disclaimer">Enter — отправить, Shift + Enter — новая строка</p>
      </div>
    </aside>
  )
}
