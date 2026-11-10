import type { AbsenceType, Role } from '../api/schemas'

const ROLE_LABELS: Record<Role, string> = {
  intern: 'Стажёр',
  mentor: 'Наставник',
  manager: 'Руководитель',
  hr_bp: 'HR BP',
}

export function roleLabel(role: Role): string {
  return ROLE_LABELS[role]
}

const ABSENCE_TYPE_LABELS: Record<AbsenceType, string> = {
  day_off: 'Отгул',
  vacation: 'Отпуск',
  sick: 'Больничный',
}

export function absenceTypeLabel(type: AbsenceType): string {
  return ABSENCE_TYPE_LABELS[type]
}

export type BadgeTone = 'neutral' | 'warning' | 'success' | 'danger'

interface StatusMeta {
  label: string
  tone: BadgeTone
}

const ABSENCE_STATUS_META: Record<string, StatusMeta> = {
  draft: { label: 'Черновик', tone: 'neutral' },
  created: { label: 'Создана', tone: 'neutral' },
  pending_approval: { label: 'На согласовании', tone: 'warning' },
  approved: { label: 'Согласована', tone: 'success' },
  rejected: { label: 'Отклонена', tone: 'danger' },
  cancelled: { label: 'Отменена', tone: 'neutral' },
}

export function absenceStatusMeta(status: string): StatusMeta {
  return ABSENCE_STATUS_META[status] ?? { label: status, tone: 'neutral' }
}

const dateFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })
const shortDateFormatter = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit' })

export function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return dateFormatter.format(date)
}

export function formatDateRange(from: string, to: string): string {
  if (from === to) return formatDate(from)
  return `${formatDate(from)} — ${formatDate(to)}`
}

export function formatShortDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return shortDateFormatter.format(date)
}

const timeFormatter = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })

export function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return timeFormatter.format(date)
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function todayIso(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10)
}
