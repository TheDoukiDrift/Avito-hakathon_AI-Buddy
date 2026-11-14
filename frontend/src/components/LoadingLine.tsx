interface LoadingLineProps {
  /** «Загрузка», «Загружаем чек-лист» — что именно ждём. */
  label?: string
}

/**
 * Строка загрузки: три точки в цвете forest. Состояние ожидания видимое,
 * но интерфейс не блокирует; при prefers-reduced-motion анимация выключается.
 */
export function LoadingLine({ label = 'Загрузка' }: LoadingLineProps) {
  return (
    <p className="loading-line" role="status">
      {label}
      <span className="typing" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </p>
  )
}
