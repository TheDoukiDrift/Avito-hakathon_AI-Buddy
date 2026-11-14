/**
 * Иконки дизайн-системы «Годовые кольца» — собственные SVG, без внешних
 * библиотек (решение дизайнера: штрих 1.8, скруглённые концы, viewBox 24×24).
 */

export type IconName =
  | 'home'
  | 'route'
  | 'book'
  | 'chat'
  | 'send'
  | 'check'
  | 'clock'
  | 'x'
  | 'shield'
  | 'lock'
  | 'arrow'
  | 'people'
  | 'file'

const ICONS: Record<IconName, string[]> = {
  home: ['M3 11.5 12 4l9 7.5', 'M5.5 10v9.5h13V10', 'M10 19.5v-5h4v5'],
  route: [
    'M4.5 6a1.5 1.5 0 1 0 3 0 1.5 1.5 0 1 0-3 0Z',
    'M16.5 19a1.5 1.5 0 1 0 3 0 1.5 1.5 0 1 0-3 0Z',
    'M7.5 6H14a3.5 3.5 0 0 1 0 7h-4a3.5 3.5 0 0 0 0 6h6.5',
  ],
  book: [
    'M12 6.5C10 5 7.5 4.5 4.5 5v13c3-.5 5.5 0 7.5 1.5 2-1.5 4.5-2 7.5-1.5V5c-3-.5-5.5 0-7.5 1.5Z',
    'M12 6.5v13',
  ],
  chat: ['M20 12a8 8 0 0 1-11.7 7.1L4 20l1-3.9A8 8 0 1 1 20 12Z', 'M9 11.5h6M9 14.5h3.5'],
  send: ['M20.5 3.5 3.5 10.5l6.5 3 3 6.5 7.5-16.5Z', 'M10 13.5l10.5-10'],
  check: ['M5 12.5 10 17.5 19 7'],
  clock: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M12 7v5l3 2'],
  x: ['M6 6l12 12M18 6 6 18'],
  shield: ['M12 3 5 6v5.5c0 4.2 2.8 7.5 7 9.5 4.2-2 7-5.3 7-9.5V6l-7-3Z', 'M9 12l2 2 4-4'],
  lock: ['M6 11h12v9H6Z', 'M8.5 11V8a3.5 3.5 0 0 1 7 0v3'],
  arrow: ['M5 12h14M13 6l6 6-6 6'],
  people: [
    'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
    'M2.5 20c0-3.3 2.7-6 6.5-6s6.5 2.7 6.5 6',
    'M16 4.5a3.2 3.2 0 0 1 0 6.3',
    'M18 14.2c2 .6 3.5 2.6 3.5 5.8',
  ],
  file: ['M7 3.5h7l4 4V20.5H7Z', 'M14 3.5v4h4', 'M10 12h5M10 16h5'],
}

interface IconProps {
  name: IconName
  size?: number
}

export function Icon({ name, size = 18 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {ICONS[name].map((d, index) => (
        <path key={index} d={d} />
      ))}
    </svg>
  )
}
