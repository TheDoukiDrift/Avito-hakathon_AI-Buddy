interface InlineErrorProps {
  /** Деталь ошибки: текст ApiError, сообщение сети или запасная строка. */
  message: string
  /** Повтор запроса/мутации. Без обработчика кнопка не рисуется. */
  onRetry?: () => void
  /** «Ошибка загрузки» для запросов, «Ошибка» для действий. */
  prefix?: string
}

/**
 * Плоская строка ошибки: волосяная рамка accent-red, моноширинный текст,
 * кнопка «ПОВТОРИТЬ» на инверсии. Без модалок, тостов и скруглений.
 */
export function InlineError({ message, onRetry, prefix = 'Ошибка загрузки' }: InlineErrorProps) {
  return (
    <div className="inline-error" role="alert">
      <span className="inline-error__text">
        {prefix}: {message}
      </span>
      {onRetry ? (
        <button className="inline-error__retry" type="button" onClick={onRetry}>
          ПОВТОРИТЬ
        </button>
      ) : null}
    </div>
  )
}
