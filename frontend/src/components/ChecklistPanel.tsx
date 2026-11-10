import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import type { ChecklistItem } from '../api/schemas'
import {
  checklistProgress,
  groupChecklistByWeek,
  nextPendingItem,
  weekLabel,
} from '../utils/checklist'

export function ChecklistPanel() {
  const queryClient = useQueryClient()

  const checklistQuery = useQuery({
    queryKey: ['checklist'],
    queryFn: api.fetchChecklist,
  })

  const completeMutation = useMutation({
    mutationFn: api.completeChecklistItem,
    onSuccess: (updated) => {
      queryClient.setQueryData<ChecklistItem[]>(['checklist'], (current = []) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      )
    },
  })

  const items = checklistQuery.data ?? []
  const groups = groupChecklistByWeek(items)
  const progress = checklistProgress(items)
  const nextItem = nextPendingItem(items)

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
        <span className="panel__percent">{progress.percent}%</span>
      </div>
      <p className="panel__subtitle">
        {progress.total > 0
          ? `Выполнено ${progress.done} из ${progress.total}`
          : 'Этапы адаптации по неделям'}
      </p>

      <div className="progress" aria-hidden="true">
        <span className="progress__bar" style={{ width: `${progress.percent}%` }} />
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
        <div className="next-step">
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
