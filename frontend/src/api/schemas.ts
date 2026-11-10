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

export const checklistResponseSchema = z.object({
  items: z.array(checklistItemSchema),
})
export type ChecklistResponse = z.infer<typeof checklistResponseSchema>

export const absenceTypeSchema = z.enum(['day_off', 'vacation', 'sick'])
export type AbsenceType = z.infer<typeof absenceTypeSchema>

/**
 * Статус заявки приходит из имитации корпоративного сервиса: черновик →
 * согласование → финальные состояния. Список расширяемый, поэтому строку
 * валидируем мягко, а подпись для UI подбираем в utils/labels.
 */
export const absenceSchema = z.object({
  id: idSchema,
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

export const apiErrorSchema = z.object({
  detail: z.string(),
})
