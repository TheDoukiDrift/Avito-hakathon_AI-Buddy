import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from './client'

const fetchMock = vi.fn()

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  api.setUnauthorizedHandler(null)
})

describe('SSE-парсер', () => {
  it('разделяет события между чанками и сохраняет хвост', () => {
    const first = api.splitSseEvents('data: {"token":"При"}\n\ndata: {"tok')
    expect(first.events).toEqual(['data: {"token":"При"}'])
    expect(first.rest).toBe('data: {"tok')

    const second = api.splitSseEvents(`${first.rest}en":"вет"}\n\n`)
    expect(second.events).toEqual(['data: {"token":"вет"}'])
    expect(second.rest).toBe('')
  })

  it('достаёт token и игнорирует мусор и [DONE]', () => {
    expect(api.parseSseEvent('data: {"token":"привет"}')).toBe('привет')
    expect(api.parseSseEvent('data: [DONE]')).toBeNull()
    expect(api.parseSseEvent('data: not-json')).toBeNull()
    expect(api.parseSseEvent('event: ping')).toBeNull()
  })
})

describe('HTTP-клиент', () => {
  it('логинит и парсит пользователя', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        token: 'jwt-token',
        user: { id: 7, email: 'a@b.ru', role: 'intern', full_name: 'Иван Петров' },
      }),
    )

    const result = await api.login(' a@b.ru ', 'test1234')

    expect(result.user.id).toBe('7')
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/auth/login')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      email: ' a@b.ru ',
      password: 'test1234',
    })
  })

  it('разбирает ответы всех эндпоинтов контракта', async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse([{ id: 1, role: 'user', content: 'привет', created_at: '2026-11-10T10:00:00Z' }]),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ id: 5, week: 1, title: 'Цели', description: '', status: 'done' }],
          next_item: null,
          done_count: 1,
          total: 1,
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ id: 5, week: 1, title: 'Цели', description: '', status: 'done' }))
      .mockResolvedValueOnce(
        jsonResponse({
          id: 9,
          type: 'day_off',
          date_from: '2026-11-11',
          date_to: '2026-11-11',
          reason: '',
          status: 'draft',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: '9',
          type: 'day_off',
          date_from: '2026-11-11',
          date_to: '2026-11-11',
          reason: '',
          status: 'pending_approval',
        }),
      )
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 3, name: 'Анна Смирнова', role: 'Наставник', team: 'Core', email: 'a@b.ru' },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          reminders: [
            {
              id: 7,
              checklist_item_id: 5,
              message: 'Составьте план на неделю',
              created_at: '2026-11-10T10:00:00Z',
            },
          ],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ id: 7, acked: true }))

    await expect(api.fetchChatHistory()).resolves.toHaveLength(1)
    await expect(api.getChecklist()).resolves.toMatchObject({
      done_count: 1,
      total: 1,
      next_item: null,
    })
    await expect(api.completeChecklistItem('5')).resolves.toMatchObject({ status: 'done' })
    await expect(
      api.createAbsence({
        type: 'day_off',
        date_from: '2026-11-11',
        date_to: '2026-11-11',
        reason: '',
      }),
    ).resolves.toMatchObject({ status: 'draft' })
    await expect(api.confirmAbsence('9')).resolves.toMatchObject({ status: 'pending_approval' })
    await expect(api.fetchAbsences()).resolves.toEqual([])
    await expect(api.fetchContacts()).resolves.toHaveLength(1)
    await expect(api.getReminders()).resolves.toMatchObject([{ id: '7', checklist_item_id: '5' }])
    await expect(api.ackReminder('7')).resolves.toEqual({ id: '7', acked: true })

    expect(fetchMock.mock.calls.map((call) => (call as [string])[0])).toEqual([
      '/api/chat/history',
      '/api/checklist',
      '/api/checklist/5/complete',
      '/api/absences',
      '/api/absences/9/confirm',
      '/api/absences',
      '/api/contacts',
      '/api/reminders',
      '/api/reminders/7/ack',
    ])
  })

  it('оборачивает старый ответ чек-листа массивом', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        { id: 1, week: 1, title: 'Цели', description: '', status: 'done' },
        { id: 2, week: 1, title: 'Составить план', description: '', status: 'pending' },
      ]),
    )

    const checklist = await api.getChecklist()

    expect(checklist.total).toBe(2)
    expect(checklist.done_count).toBe(1)
    expect(checklist.next_item).toMatchObject({ id: '2', title: 'Составить план', week: 1 })
  })

  it('принимает минимальные ответы по заявкам из контракта', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ id: 9, status: 'draft' }))
      .mockResolvedValueOnce(jsonResponse({ id: '9', status: 'pending_approval' }))

    await expect(
      api.createAbsence({
        type: 'sick',
        date_from: '2026-11-11',
        date_to: '2026-11-12',
        reason: '',
      }),
    ).resolves.toMatchObject({ id: '9', status: 'draft' })

    await expect(api.confirmAbsence('9')).resolves.toMatchObject({
      id: '9',
      status: 'pending_approval',
    })
  })

  it('показывает detail из ошибки 403', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Недостаточно прав для этого действия' }, 403),
    )

    await expect(api.getChecklist()).rejects.toMatchObject({
      status: 403,
      message: 'Недостаточно прав для этого действия',
    })
  })

  it('на 401 чистит токен и вызывает обработчик разлогина', async () => {
    const handler = vi.fn()
    api.setUnauthorizedHandler(handler)
    api.setToken('jwt-token')
    fetchMock.mockResolvedValueOnce(new Response('', { status: 401 }))

    await expect(api.fetchMe()).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
    expect(api.getToken()).toBeNull()
  })

  it('оборачивает сетевую ошибку и неожиданный ответ', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('network down'))
    await expect(api.fetchMe()).rejects.toMatchObject({ status: 0 })

    fetchMock.mockResolvedValueOnce(jsonResponse({ unexpected: true }))
    await expect(api.fetchContacts()).rejects.toMatchObject({ status: 200 })
  })
})

describe('streamChat', () => {
  it('собирает токены из потока SSE', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"token":"При"}\n\n'))
        controller.enqueue(encoder.encode('data: {"token":"вет"}\n\n'))
        controller.close()
      },
    })
    fetchMock.mockResolvedValueOnce(new Response(stream, { status: 200 }))

    const tokens: string[] = []
    await api.streamChat('привет', (token) => tokens.push(token))

    expect(tokens).toEqual(['При', 'вет'])
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/chat/stream')
    expect(JSON.parse(String(init.body))).toEqual({ message: 'привет' })
  })

  it('бросает ошибку, если поток недоступен', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 200 }))
    await expect(api.streamChat('привет', () => undefined)).rejects.toMatchObject({ status: 0 })
  })
})
