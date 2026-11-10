import { describe, expect, it } from 'vitest'
import {
  absenceSchema,
  chatMessageSchema,
  checklistItemSchema,
  loginResponseSchema,
} from './schemas'

const validUser = {
  id: 1,
  email: 'intern@example.com',
  role: 'intern',
  full_name: 'Иван Петров',
}

describe('loginResponseSchema', () => {
  it('принимает корректный ответ и приводит id к строке', () => {
    const parsed = loginResponseSchema.parse({ token: 'jwt-token', user: validUser })

    expect(parsed.token).toBe('jwt-token')
    expect(parsed.user.id).toBe('1')
    expect(parsed.user.role).toBe('intern')
  })

  it('отклоняет неизвестную роль и пустой токен', () => {
    expect(
      loginResponseSchema.safeParse({
        token: '',
        user: { ...validUser, role: 'admin' },
      }).success,
    ).toBe(false)

    expect(
      loginResponseSchema.safeParse({ token: 'jwt-token', user: { ...validUser, email: 'nope' } })
        .success,
    ).toBe(false)
  })
})

describe('доменные схемы', () => {
  it('подставляет пустое описание пункта чек-листа', () => {
    const item = checklistItemSchema.parse({
      id: 3,
      week: 1,
      title: 'Обсудить цели с руководителем',
      status: 'pending',
    })

    expect(item.description).toBe('')
    expect(item.week).toBe(1)
  })

  it('принимает статус заявки строкой и типы отсутствий из контракта', () => {
    const absence = absenceSchema.parse({
      id: '42',
      type: 'day_off',
      date_from: '2026-11-11',
      date_to: '2026-11-11',
      reason: 'Личные дела',
      status: 'pending_approval',
    })

    expect(absence.id).toBe('42')
    expect(absence.status).toBe('pending_approval')
    expect(
      absenceSchema.safeParse({ ...absence, type: 'business_trip' }).success,
    ).toBe(false)
  })

  it('отклоняет сообщение чата с ролью system', () => {
    expect(
      chatMessageSchema.safeParse({
        id: 1,
        role: 'system',
        content: '…',
        created_at: '2026-11-10T10:00:00Z',
      }).success,
    ).toBe(false)
  })
})
