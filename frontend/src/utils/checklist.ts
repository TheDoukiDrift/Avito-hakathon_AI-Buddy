import type { ChecklistItem } from '../api/schemas'

export interface ChecklistGroup {
  week: number
  items: ChecklistItem[]
}

/** Группирует пункты чек-листа по неделям, недели — по возрастанию, порядок внутри — серверный. */
export function groupChecklistByWeek(items: ChecklistItem[]): ChecklistGroup[] {
  const groups = new Map<number, ChecklistItem[]>()

  for (const item of items) {
    const bucket = groups.get(item.week)
    if (bucket) {
      bucket.push(item)
    } else {
      groups.set(item.week, [item])
    }
  }

  return [...groups.entries()]
    .sort(([a], [b]) => a - b)
    .map(([week, weekItems]) => ({ week, items: weekItems }))
}

/** Первый невыполненный пункт в порядке недель — «следующий шаг» для панели. */
export function nextPendingItem(items: ChecklistItem[]): ChecklistItem | undefined {
  for (const group of groupChecklistByWeek(items)) {
    const pending = group.items.find((item) => item.status === 'pending')
    if (pending) return pending
  }
  return undefined
}

export interface ChecklistProgress {
  done: number
  total: number
  percent: number
}

export function checklistProgress(items: ChecklistItem[]): ChecklistProgress {
  const total = items.length
  const done = items.filter((item) => item.status === 'done').length
  return { done, total, percent: total === 0 ? 0 : Math.round((done / total) * 100) }
}

export function weekLabel(week: number): string {
  return `Неделя ${week}`
}
