interface LoadingLineProps {
  /** «Загрузка», «Загружаем чек-лист» — рисуется капсом через CSS. */
  label?: string
}

/**
 * Строка загрузки: единственная анимация документа — мигающий курсор.
 * Никаких спиннеров и полос.
 */
export function LoadingLine({ label = 'Загрузка' }: LoadingLineProps) {
  return (
    <p className="loading-line" role="status">
      {label}{' '}
      <span className="blink" aria-hidden="true">
        ▋
      </span>
    </p>
  )
}
