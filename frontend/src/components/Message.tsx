import type { ChatMessage } from '../api/schemas'
import { formatTime } from '../utils/labels'

interface MessageProps {
  message: ChatMessage
  streaming?: boolean
}

export function Message({ message, streaming = false }: MessageProps) {
  const isUser = message.role === 'user'
  const hasContent = message.content.trim().length > 0

  return (
    <article className={`message ${isUser ? 'message--user' : 'message--assistant'}`}>
      <span className="message__role">{isUser ? 'Вы' : 'Бадди'}</span>
      <div className="message__body">
        <div className="message__text">
          {hasContent ? message.content : null}
          {streaming ? (
            <span className="blink" aria-hidden="true">
              ▋
            </span>
          ) : null}
        </div>
        <div className="message__meta">
          {isUser ? 'Вы' : 'AI-buddy'}
          {message.created_at ? ` · ${formatTime(message.created_at)}` : ''}
        </div>
      </div>
    </article>
  )
}
