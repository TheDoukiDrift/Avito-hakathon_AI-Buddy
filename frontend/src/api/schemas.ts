import { z } from 'zod'

/** Идентификаторы бэкенд может отдавать числом или строкой — приводим к строке. */
const idSchema = z
  .union([z.string(), z.number()])
  .transform((value) => String(value))

export const roleSchema = z.enum(['intern', 'mentor', 'manager', 'hr_bp'])
export type Role = z.infer<typeof roleSchema>

export const userSchema = z.object({
  id: idSchema,
  email: z.string().email(),
  role: roleSchema,
  full_name: z.string().min(1),
})
export type User = z.infer<typeof userSchema>

export const loginResponseSchema = z.object({
  token: z.string().min(1),
  user: userSchema,
})
export type LoginResponse = z.infer<typeof loginResponseSchema>

export const chatRoleSchema = z.enum(['user', 'assistant'])
export type ChatRole = z.infer<typeof chatRoleSchema>

export const chatMessageSchema = z.object({
  id: idSchema,
  role: chatRoleSchema,
  content: z.string(),
  created_at: z.string(),
})
export type ChatMessage = z.infer<typeof chatMessageSchema>

export const chatHistorySchema = z.array(chatMessageSchema)

export const checklistItemSchema = z.object({
  id: idSchema,
  week: z.coerce.number().int().nonnegative(),
  title: z.string().min(1),
  description: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  status: z.enum(['pending', 'done']),
})
export type ChecklistItem = z.infer<typeof checklistItemSchema>

/** Бэкенд сам считает «следующий шаг» — клиент его не переопределяет. */
export const nextChecklistItemSchema = z.object({
  id: idSchema,
  title: z.string().min(1),
  week: z.coerce.number().int().nonnegative(),
})
export type NextChecklistItem = z.infer<typeof nextChecklistItemSchema>

export interface ChecklistResponse {
  items: ChecklistItem[]
  next_item: NextChecklistItem | null
  done_count: number
  total: number
}

const checklistEnvelopeSchema = z.object({
  items: z.array(checklistItemSchema),
  next_item: nextChecklistItemSchema.nullable().optional(),
  done_count: z.coerce.number().int().nonnegative().optional(),
  total: z.coerce.number().int().nonnegative().optional(),
})

/** Первый невыполненный пункт по (неделя, серверный порядок) — только для старого ответа. */
function firstPendingItem(items: ChecklistItem[]): NextChecklistItem | null {
  const ordered = [...items].sort((a, b) => a.week - b.week)
  const pending = ordered.find((item) => item.status === 'pending')
  return pending ? { id: pending.id, title: pending.title, week: pending.week } : null
}

/**
 * Контракт отдаёт объект с метаданными прогресса, но ранние сборки бэкенда
 * возвращали голый массив. Массив оборачиваем на клиенте, а недостающие
 * метаданные считаем по пунктам — интерфейс обязан работать с любым из двух.
 */
export const checklistResponseSchema = z
  .union([z.array(checklistItemSchema), checklistEnvelopeSchema])
  .transform((payload): ChecklistResponse => {
    if (Array.isArray(payload)) {
      const done = payload.filter((item) => item.status === 'done').length
      return {
        items: payload,
        next_item: firstPendingItem(payload),
        done_count: done,
        total: payload.length,
      }
    }

    const done = payload.items.filter((item) => item.status === 'done').length
    return {
      items: payload.items,
      next_item:
        payload.next_item === undefined ? firstPendingItem(payload.items) : payload.next_item,
      done_count: payload.done_count ?? done,
      total: payload.total ?? payload.items.length,
    }
  })

export const absenceTypeSchema = z.enum(['day_off', 'vacation', 'sick'])
export type AbsenceType = z.infer<typeof absenceTypeSchema>

/**
 * Статус заявки приходит из имитации корпоративного сервиса: черновик →
 * согласование → финальные состояния. Список расширяемый, поэтому строку
 * валидируем мягко, а подпись для UI подбираем в utils/labels.
 */
export const absenceSchema = z.object({
  id: idSchema,
  /**
   * Владелец заявки. Нужен, чтобы решать чужие заявки и не предлагать
   * согласование собственной: бэкенд self-approval запрещает.
   */
  user_id: idSchema.optional(),
  type: absenceTypeSchema,
  date_from: z.string(),
  date_to: z.string(),
  reason: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  status: z.string().min(1),
})
export type Absence = z.infer<typeof absenceSchema>

/**
 * POST /absences по контракту может вернуть только черновик (id + status),
 * без остальных полей. Недостающие значения подставляет форма.
 */
export const absenceDraftResponseSchema = z.object({
  id: idSchema,
  type: absenceTypeSchema.optional(),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  reason: z.string().nullish(),
  status: z.string().min(1),
})
export type AbsenceDraftResponse = z.infer<typeof absenceDraftResponseSchema>

/** POST /absences/{id}/confirm возвращает {id, status} — остальное уже есть в форме. */
export const absenceStatusUpdateSchema = z
  .object({
    id: idSchema,
    status: z.string().min(1),
  })
  .passthrough()
export type AbsenceStatusUpdate = z.infer<typeof absenceStatusUpdateSchema>

export const absencesSchema = z.array(absenceSchema)

export const contactSchema = z.object({
  id: idSchema,
  name: z.string().min(1),
  role: z.string().min(1),
  team: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  email: z.string().email(),
})
export type Contact = z.infer<typeof contactSchema>

export const contactsSchema = z.array(contactSchema)

/** Напоминание, которое AI-крон оставил пользователю по пункту чек-листа. */
export const reminderSchema = z.object({
  id: idSchema,
  checklist_item_id: idSchema,
  message: z.string().min(1),
  created_at: z.string(),
})
export type Reminder = z.infer<typeof reminderSchema>

export const remindersResponseSchema = z.object({
  reminders: z.array(reminderSchema),
})
export type RemindersResponse = z.infer<typeof remindersResponseSchema>

export const reminderAckSchema = z.object({
  id: idSchema,
  acked: z.boolean(),
})
export type ReminderAck = z.infer<typeof reminderAckSchema>

export const apiErrorSchema = z.object({
  detail: z.string(),
})
