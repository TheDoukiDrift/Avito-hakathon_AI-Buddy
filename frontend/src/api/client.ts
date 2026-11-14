import { z } from 'zod'
import {
  absenceDraftResponseSchema,
  absencesSchema,
  absenceStatusUpdateSchema,
  apiErrorSchema,
  chatHistorySchema,
  checklistItemSchema,
  checklistResponseSchema,
  contactsSchema,
  loginResponseSchema,
  reminderAckSchema,
  remindersResponseSchema,
  userSchema,
  type Absence,
  type AbsenceDraftResponse,
  type AbsenceStatusUpdate,
  type AbsenceType,
  type ChatMessage,
  type ChecklistItem,
  type ChecklistResponse,
  type Contact,
  type LoginResponse,
  type Reminder,
  type ReminderAck,
  type User,
} from './schemas'

const API_BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/+$/, '')
export const TOKEN_STORAGE_KEY = 'ai-buddy.token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // localStorage может быть недоступен (приватный режим) — работаем без него.
  }
}

type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/** authStore регистрирует обработчик, чтобы 401 разлогинивал пользователя. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

function handleUnauthorized(): void {
  setToken(null)
  unauthorizedHandler?.()
}

function errorMessageFromBody(body: string): string | null {
  if (!body) return null
  try {
    const parsed = apiErrorSchema.safeParse(JSON.parse(body))
    if (parsed.success) return parsed.data.detail
  } catch {
    // Тело не JSON — вернём как есть ниже.
  }
  return body.length > 300 ? `${body.slice(0, 300)}…` : body
}

async function toApiError(response: Response): Promise<ApiError> {
  let message: string | null = null
  try {
    message = errorMessageFromBody(await response.text())
  } catch {
    message = null
  }
  return new ApiError(response.status, message ?? `Ошибка запроса (${response.status})`)
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  /** Логин: 401 здесь — неверная пара, а не истёкшая сессия. */
  unauthorizedMessage?: string
}

async function request<T>(
  path: string,
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Сервис недоступен. Проверьте соединение и попробуйте ещё раз.')
  }

  if (response.status === 401) {
    // Логин обрабатывает 401 сам: без разлогина и чужого текста про сессию.
    if (options.unauthorizedMessage) {
      throw new ApiError(401, options.unauthorizedMessage)
    }
    handleUnauthorized()
    throw new ApiError(401, 'Сессия истекла. Войдите заново.')
  }

  if (!response.ok) throw await toApiError(response)

  const payload: unknown = await response.json().catch(() => null)
  const parsed = schema.safeParse(payload)
  if (!parsed.success) {
    throw new ApiError(
      response.status,
      'Сервис вернул неожиданный ответ. Обновите страницу или попробуйте позже.',
    )
  }
  return parsed.data
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return request('/auth/login', loginResponseSchema, {
    method: 'POST',
    body: { email, password },
    unauthorizedMessage: 'Неверная почта или пароль.',
  })
}

export function fetchMe(): Promise<User> {
  return request('/me', userSchema)
}

export function fetchChatHistory(): Promise<ChatMessage[]> {
  return request('/chat/history', chatHistorySchema)
}

export function getChecklist(): Promise<ChecklistResponse> {
  return request('/checklist', checklistResponseSchema)
}

export function completeChecklistItem(id: string): Promise<ChecklistItem> {
  return request(`/checklist/${encodeURIComponent(id)}/complete`, checklistItemSchema, {
    method: 'POST',
  })
}

export function getReminders(): Promise<Reminder[]> {
  return request('/reminders', remindersResponseSchema).then((data) => data.reminders)
}

export function ackReminder(id: string): Promise<ReminderAck> {
  return request(`/reminders/${encodeURIComponent(id)}/ack`, reminderAckSchema, {
    method: 'POST',
  })
}

export interface CreateAbsenceInput {
  type: AbsenceType
  date_from: string
  date_to: string
  reason: string
}

export function createAbsence(input: CreateAbsenceInput): Promise<AbsenceDraftResponse> {
  return request('/absences', absenceDraftResponseSchema, {
    method: 'POST',
    body: input,
  })
}

export function confirmAbsence(id: string): Promise<AbsenceStatusUpdate> {
  return request(`/absences/${encodeURIComponent(id)}/confirm`, absenceStatusUpdateSchema, {
    method: 'POST',
  })
}

export function fetchAbsences(): Promise<Absence[]> {
  return request('/absences', absencesSchema)
}

/**
 * Решение по чужой заявке: согласовать или отклонить. Тело пустое —
 * решение однозначно определяет сам эндпоинт.
 */
export function approveAbsence(id: string): Promise<AbsenceStatusUpdate> {
  return request(`/absences/${encodeURIComponent(id)}/approve`, absenceStatusUpdateSchema, {
    method: 'POST',
    body: {},
  })
}

export function rejectAbsence(id: string): Promise<AbsenceStatusUpdate> {
  return request(`/absences/${encodeURIComponent(id)}/reject`, absenceStatusUpdateSchema, {
    method: 'POST',
    body: {},
  })
}

export function fetchContacts(): Promise<Contact[]> {
  return request('/contacts', contactsSchema)
}

/** Разбирает SSE-буфер на завершённые события; хвост возвращает для следующего чанка. */
export function splitSseEvents(buffer: string): { events: string[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const rest = parts.pop() ?? ''
  return { events: parts.filter((part) => part.trim().length > 0), rest }
}

/** Достаёт token из одного SSE-события вида `data: {"token":"…"}`. */
export function parseSseEvent(event: string): string | null {
  const data = event
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
    .trim()

  if (!data || data === '[DONE]') return null

  try {
    const parsed = z.object({ token: z.string() }).safeParse(JSON.parse(data))
    return parsed.success ? parsed.data.token : null
  } catch {
    return null
  }
}

/**
 * Стрим ответа бадди. fetch + ReadableStream вместо EventSource: нужен
 * POST-запрос с телом и заголовком Authorization.
 */
export async function streamChat(
  message: string,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    'Content-Type': 'application/json',
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Сервис недоступен. Проверьте соединение и попробуйте ещё раз.')
  }

  if (response.status === 401) {
    handleUnauthorized()
    throw new ApiError(401, 'Сессия истекла. Войдите заново.')
  }

  if (!response.ok) throw await toApiError(response)

  if (!response.body) {
    throw new ApiError(0, 'Браузер не поддерживает потоковый ответ. Обновите браузер.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const consume = (events: string[]) => {
    for (const event of events) {
      const token = parseSseEvent(event)
      if (token !== null) onToken(token)
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { events, rest } = splitSseEvents(buffer)
      buffer = rest
      consume(events)
    }
    buffer += decoder.decode()
    if (buffer.trim()) consume([buffer])
  } finally {
    reader.releaseLock()
  }
}
