import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import type { ChecklistResponse } from '../api/schemas'
import { checklistProgress, groupChecklistByWeek, nextPendingItem, weekLabel } from '../utils/checklist'

export function ChecklistPanel() {
  const queryClient = useQueryClient()

  const checklistQuery = useQuery({
    queryKey: ['checklist'],
    queryFn: api.getChecklist,
  })

  const completeMutation = useMutation({
    mutationFn: api.completeChecklistItem,
    onSuccess: (updated) => {
      // Сразу показываем результат, затем сверяемся с сервером: next_item и
      // счётчики считает бэкенд, клиент лишь временно повторяет его арифметику.
      queryClient.setQueryData<ChecklistResponse>(['checklist'], (current) => {
        if (!current) return current
        const items = current.items.map((item) => (item.id === updated.id ? updated : item))
        const progress = checklistProgress(items)
        const next = nextPendingItem(items)
        return {
          items,
          next_item: next ? { id: next.id, title: next.title, week: next.week } : null,
          done_count: progress.done,
          total: progress.total,
        }
      })
      void queryClient.invalidateQueries({ queryKey: ['checklist'] })
    },
  })

  const items = checklistQuery.data?.items ?? []
  const groups = groupChecklistByWeek(items)
  const nextItem = checklistQuery.data?.next_item ?? null
  const done = checklistQuery.data?.done_count ?? 0
  const total = checklistQuery.data?.total ?? 0
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)

  const loadError =
    checklistQuery.error instanceof Error
      ? checklistQuery.error.message
      : checklistQuery.isError
        ? 'Не удалось загрузить чек-лист.'
        : null

  return (
    <section className="panel" aria-label="Чек-лист адаптации">
      <div className="sec-head sec-head--sm">
        <span className="sec-num">02 —</span>
        <h2 className="sec-title">Чек-лист</h2>
        <span className="sec-rule" />
        <span className="panel__percent">{percent}%</span>
      </div>
      <p className="panel__subtitle">
        {total > 0 ? `Выполнено ${done} из ${total}` : 'Этапы адаптации по неделям'}
      </p>

      <div
        className="progress"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Прогресс адаптации"
      >
        <span className="progress__bar" style={{ width: `${percent}%` }} />
      </div>

      {checklistQuery.isLoading ? <p className="panel__placeholder">Загружаем чек-лист…</p> : null}

      {loadError ? (
        <p className="inline-error" role="alert">
          {loadError}
        </p>
      ) : null}

      {!checklistQuery.isLoading && !loadError && items.length === 0 ? (
        <p className="panel__placeholder">В чек-листе пока нет пунктов.</p>
      ) : null}

      {nextItem ? (
        <div className="next-step" aria-label="Следующий шаг">
          <span className="next-step__label">Следующий шаг</span>
          <p className="next-step__title">{nextItem.title}</p>
          <p className="next-step__meta">{weekLabel(nextItem.week)}</p>
        </div>
      ) : null}

      <div className="checklist">
        {groups.map((group) => (
          <div key={group.week} className="checklist__week">
            <h3 className="checklist__week-title">{weekLabel(group.week)}</h3>
            <ul className="checklist__list">
              {group.items.map((item) => {
                const done = item.status === 'done'
                const pendingThisItem = completeMutation.isPending && completeMutation.variables === item.id
                return (
                  <li key={item.id} className={`checklist__item ${done ? 'checklist__item--done' : ''}`}>
                    <label className="checklist__label">
                      <input
                        type="checkbox"
                        className="checklist__checkbox"
                        checked={done}
                        disabled={done || pendingThisItem}
                        onChange={() => completeMutation.mutate(item.id)}
                      />
                      <span className="checklist__content">
                        <span className="checklist__title">{item.title}</span>
                        {item.description ? (
                          <span className="checklist__description">{item.description}</span>
                        ) : null}
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>

      {completeMutation.isError ? (
        <p className="inline-error" role="alert">
          {completeMutation.error instanceof Error
            ? completeMutation.error.message
            : 'Не удалось отметить пункт.'}
        </p>
      ) : null}
    </section>
  )
}
