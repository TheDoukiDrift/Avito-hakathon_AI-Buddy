import { describe, expect, it } from 'vitest'
import {
  absenceSchema,
  chatMessageSchema,
  checklistItemSchema,
  checklistResponseSchema,
  loginResponseSchema,
  reminderAckSchema,
  remindersResponseSchema,
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

describe('checklistResponseSchema', () => {
  const items = [
    { id: 1, week: 1, title: 'Обсудить цели', description: '', status: 'done' },
    { id: 2, week: 1, title: 'Составить план', description: 'Черновик', status: 'pending' },
    { id: 3, week: 2, title: 'Запросить доступы', status: 'pending' },
  ]

  it('принимает конверт с next_item и счётчиками', () => {
    const parsed = checklistResponseSchema.parse({
      items,
      next_item: { id: 3, title: 'Запросить доступы', week: 2 },
      done_count: 1,
      total: 3,
    })

    expect(parsed.items).toHaveLength(3)
    expect(parsed.next_item).toEqual({ id: '3', title: 'Запросить доступы', week: 2 })
    expect(parsed.done_count).toBe(1)
    expect(parsed.total).toBe(3)
  })

  it('оборачивает старый ответ-массив и считает метаданные сам', () => {
    const parsed = checklistResponseSchema.parse(items)

    expect(parsed.items).toHaveLength(3)
    expect(parsed.next_item).toEqual({ id: '2', title: 'Составить план', week: 1 })
    expect(parsed.done_count).toBe(1)
    expect(parsed.total).toBe(3)
  })

  it('достраивает метаданные, если конверт пришёл без них', () => {
    const parsed = checklistResponseSchema.parse({ items })

    expect(parsed.next_item?.id).toBe('2')
    expect(parsed.done_count).toBe(1)
    expect(parsed.total).toBe(3)
  })

  it('сохраняет null в next_item — клиент не придумывает шаг за сервер', () => {
    const parsed = checklistResponseSchema.parse({
      items,
      next_item: null,
      done_count: 1,
      total: 3,
    })

    expect(parsed.next_item).toBeNull()
  })
})

describe('reminders', () => {
  it('разбирает конверт со списком напоминаний', () => {
    const parsed = remindersResponseSchema.parse({
      reminders: [
        {
          id: 7,
          checklist_item_id: 2,
          message: 'Не забудьте составить план на неделю',
          created_at: '2026-11-10T10:00:00Z',
        },
      ],
    })

    expect(parsed.reminders).toHaveLength(1)
    expect(parsed.reminders[0]).toMatchObject({
      id: '7',
      checklist_item_id: '2',
      message: 'Не забудьте составить план на неделю',
    })
  })

  it('требует непустое сообщение и подтверждение в ответе ack', () => {
    expect(
      remindersResponseSchema.safeParse({
        reminders: [{ id: 7, checklist_item_id: 2, message: '', created_at: '2026-11-10' }],
      }).success,
    ).toBe(false)

    expect(reminderAckSchema.parse({ id: 7, acked: true })).toEqual({ id: '7', acked: true })
  })
})
