import { describe, expect, it } from 'vitest'
import type { ChecklistItem } from '../api/schemas'
import { checklistProgress, groupChecklistByWeek, nextPendingItem } from './checklist'

const items: ChecklistItem[] = [
  { id: '3', week: 2, title: 'Запросить инструмент у куратора', description: '', status: 'pending' },
  { id: '1', week: 1, title: 'Обсудить цели', description: '', status: 'done' },
  { id: '2', week: 1, title: 'Составить план', description: '', status: 'pending' },
  { id: '4', week: 1, title: 'Познакомиться с командой', description: '', status: 'done' },
]

describe('groupChecklistByWeek', () => {
  it('группирует по неделям по возрастанию и сохраняет серверный порядок', () => {
    const groups = groupChecklistByWeek(items)

    expect(groups.map((group) => group.week)).toEqual([1, 2])
    expect(groups[0]?.items.map((item) => item.id)).toEqual(['1', '2', '4'])
    expect(groups[1]?.items.map((item) => item.id)).toEqual(['3'])
  })

  it('возвращает пустой список для пустого чек-листа', () => {
    expect(groupChecklistByWeek([])).toEqual([])
  })
})

describe('nextPendingItem', () => {
  it('берёт первый невыполненный пункт по порядку недель', () => {
    expect(nextPendingItem(items)?.id).toBe('2')
  })

  it('возвращает undefined, когда всё выполнено', () => {
    const done = items.map((item) => ({ ...item, status: 'done' as const }))
    expect(nextPendingItem(done)).toBeUndefined()
  })
})

describe('checklistProgress', () => {
  it('считает выполненное и процент', () => {
    expect(checklistProgress(items)).toEqual({ done: 2, total: 4, percent: 50 })
  })

  it('не делит на ноль в пустом чек-листе', () => {
    expect(checklistProgress([])).toEqual({ done: 0, total: 0, percent: 0 })
  })
})
