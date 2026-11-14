import { useMemo } from 'react'

/**
 * «Годовые кольца» — фирменный образ прогресса: кольцо дня заполняется по мере
 * выполнения шагов, как годовые кольца дерева. Контур неровный, но
 * детерминированный: один seed всегда даёт один и тот же рисунок.
 */
function ringPath(r: number, seed: number, cx = 100, cy = 100): string {
  const steps = 96
  let d = ''
  for (let i = 0; i < steps; i++) {
    const angle = (i / steps) * Math.PI * 2
    const wobble =
      Math.sin(angle * 3 + seed) * 0.5 +
      Math.sin(angle * 5 + seed * 1.7) * 0.3 +
      Math.sin(angle * 2 - seed) * 0.2
    const radius = r + wobble * (1.2 + r * 0.014)
    const x = (cx + Math.cos(angle) * radius).toFixed(1)
    const y = (cy + Math.sin(angle) * radius).toFixed(1)
    d += `${i === 0 ? 'M' : 'L'}${x} ${y}`
  }
  return `${d}Z`
}

interface RingProps {
  /** Заполнение кольца в процентах (0–100). */
  percent: number
  /** Подпись для скринридеров. */
  label: string
  /** lg — кольцо дня на главной, sm — компактный индикатор. */
  size?: 'lg' | 'sm'
}

/**
 * Кольцо прогресса: трек + дуга, стартующая сверху. Значение читается и
 * визуально, и через role="progressbar".
 */
export function Ring({ percent, label, size = 'lg' }: RingProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)))
  const path = useMemo(() => ringPath(78, 2.4), [])

  return (
    <div
      className={`ring-wrap ring-wrap--${size}`}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <svg viewBox="0 0 200 200" className="ring" aria-hidden="true">
        <path d={path} className="ring__track" />
        {clamped > 0 ? (
          <g transform="rotate(-90 100 100)">
            <path
              d={path}
              pathLength={100}
              className="ring__arc"
              style={{ strokeDasharray: `${clamped} 100` }}
            />
          </g>
        ) : null}
      </svg>
      <span className="ring__value">{clamped}%</span>
    </div>
  )
}

/** Знак продукта: три вложенных кольца — тот же образ, что и в прогрессе. */
export function BrandMark() {
  const rings = useMemo(() => [9, 15, 21].map((r, i) => ringPath(r, i * 2 + 1, 24, 24)), [])

  return (
    <svg viewBox="0 0 48 48" className="brand__mark" aria-hidden="true">
      {rings.map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke="currentColor"
          strokeWidth={i === 2 ? 3 : 2.2}
          strokeLinecap="round"
          opacity={0.45 + i * 0.275}
        />
      ))}
      <circle cx="24" cy="24" r="3" fill="currentColor" />
    </svg>
  )
}

/** Аватар: инициалы в круге с кольцом — кольца живут и здесь. */
export function RingAvatar({ initials }: { initials: string }) {
  return (
    <span className="avatar" aria-hidden="true">
      <svg viewBox="0 0 48 48" className="avatar__ring">
        <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeWidth="1.6" opacity="0.55" />
        <circle cx="24" cy="24" r="17" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />
      </svg>
      <b>{initials}</b>
    </span>
  )
}

/** Знак помощника в шапке чата: мишень из колец. */
export function ChatMark() {
  return (
    <svg viewBox="0 0 48 48" className="chat__mark" aria-hidden="true">
      <circle cx="24" cy="24" r="21" fill="currentColor" opacity=".14" />
      <circle cx="24" cy="24" r="14" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <circle cx="24" cy="24" r="7" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <circle cx="24" cy="24" r="2.6" fill="currentColor" />
    </svg>
  )
}
