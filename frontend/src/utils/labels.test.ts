import { describe, expect, it } from 'vitest'
import {
  absenceStatusMeta,
  absenceTypeLabel,
  formatDate,
  formatDateRange,
  initials,
  roleLabel,
  todayIso,
} from './labels'

describe('labels', () => {
  it('переводит роли и типы отсутствий', () => {
    expect(roleLabel('intern')).toBe('Стажёр')
    expect(roleLabel('mentor')).toBe('Наставник')
    expect(roleLabel('manager')).toBe('Руководитель')
    expect(roleLabel('hr_bp')).toBe('HR BP')
    expect(absenceTypeLabel('day_off')).toBe('Отгул')
    expect(absenceTypeLabel('vacation')).toBe('Отпуск')
    expect(absenceTypeLabel('sick')).toBe('Больничный')
  })

  it('подбирает бейдж статуса и терпит неизвестный статус', () => {
    expect(absenceStatusMeta('draft')).toEqual({ label: 'Черновик', tone: 'neutral' })
    expect(absenceStatusMeta('pending_approval')).toEqual({
      label: 'На согласовании',
      tone: 'warning',
    })
    expect(absenceStatusMeta('approved')).toEqual({ label: 'Согласована', tone: 'success' })
    expect(absenceStatusMeta('some_new_status')).toEqual({
      label: 'some_new_status',
      tone: 'neutral',
    })
  })

  it('форматирует даты и диапазон', () => {
    expect(formatDate('2026-11-10T12:00:00Z')).toBe('10 ноября')
    expect(formatDateRange('2026-11-10T12:00:00Z', '2026-11-10T12:00:00Z')).toBe('10 ноября')
    expect(formatDateRange('2026-11-10T12:00:00Z', '2026-11-12T12:00:00Z')).toBe(
      '10 ноября — 12 ноября',
    )
    expect(formatDate('не дата')).toBe('не дата')
  })

  it('считает инициалы и сегодняшнюю дату в ISO', () => {
    expect(initials('Анна Смирнова')).toBe('АС')
    expect(initials('Иван')).toBe('И')
    expect(initials('  ')).toBe('')
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})
