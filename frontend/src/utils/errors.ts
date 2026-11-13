/** Одна строка ошибки для плоской плашки: detail из Error, иначе запасной текст. */
export function describeError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim().length > 0) return error.message
  return fallback
}
