import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../api/schemas'
import { formatTime } from '../utils/labels'

interface MessageProps {
  message: ChatMessage
  streaming?: boolean
}

/**
 * Ссылки в ответах бадди уходят в новую вкладку.
 * react-markdown по умолчанию вычищает опасные протоколы (javascript:, data:),
 * поэтому rehype-raw не нужен.
 */
const markdownComponents: Components = {
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  },
}

const remarkPlugins = [remarkGfm]

export function Message({ message, streaming = false }: MessageProps) {
  const isUser = message.role === 'user'
  const hasContent = message.content.trim().length > 0

  return (
    <article className={`msg ${isUser ? 'msg--user' : 'msg--assistant'}`}>
      <span className="msg__who">{isUser ? 'Вы' : 'AI-buddy'}</span>
      <div className={`msg__text ${isUser ? '' : 'msg__text--markdown'}`.trim()}>
        {hasContent ? (
          isUser ? (
            message.content
          ) : (
            <ReactMarkdown remarkPlugins={remarkPlugins} components={markdownComponents}>
              {message.content}
            </ReactMarkdown>
          )
        ) : null}
        {streaming ? (
          <span className="typing" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        ) : null}
      </div>
      <span className="msg__meta">
        {message.created_at ? formatTime(message.created_at) : ''}
      </span>
    </article>
  )
}
