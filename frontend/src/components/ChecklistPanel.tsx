import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import type { ChecklistResponse } from '../api/schemas'
import { checklistProgress, groupChecklistByWeek, nextPendingItem, weekLabel } from '../utils/checklist'
import { describeError } from '../utils/errors'
import { Icon } from './Icon'
import { InlineError } from './InlineError'
import { LoadingLine } from './LoadingLine'
import { Ring } from './Rings'

/** Сколько ближайших шагов показываем под главным — «Дальше» в карточке. */
const UPCOMING_LIMIT = 3

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
  const allDone = total > 0 && done === total
  const pending = items.filter((item) => item.status === 'pending')
  const upcoming = pending.filter((item) => item.id !== nextItem?.id).slice(0, UPCOMING_LIMIT)

  return (
    <section className="panel" aria-label="Чек-лист адаптации">
      <header className="intro">
        <p className="eyebrow">План адаптации</p>
        <h1>Мой день</h1>
        <p className="lead">
          Давай двигаться небольшими шагами: каждый выполненный пункт наполняет кольцо дня.
        </p>
      </header>

      <div className="hero">
        <div className="growth">
          <div className="growth__head">
            <span className="mono-label">Твой рост</span>
            <span className="mono-label">{percent}% кольца дня</span>
          </div>

          <Ring percent={percent} label="Прогресс адаптации" />

          <div className="growth__stats">
            <div>
              <strong>
                {done}
                <small>/{total}</small>
              </strong>
              <span>Выполнено {done} из {total}</span>
            </div>
            <div>
              <strong>
                {groups.length}
                <small> нед.</small>
              </strong>
              <span>в плане адаптации</span>
            </div>
          </div>
        </div>

        {allDone ? (
          <div className="next next--done" aria-label="Адаптация пройдена">
            <span className="mono-label mono-label--forest">Кольцо замкнуто</span>
            <h2>Адаптация пройдена</h2>
            <p>
              Все шаги плана отмечены. Дальше — самостоятельная работа: если остались вопросы,
              спроси бадди или наставника.
            </p>
            <div className="chips">
              <span className="tag">{done} из {total}</span>
            </div>
          </div>
        ) : nextItem ? (
          <div className="next" aria-label="Следующий шаг">
            <span className="mono-label mono-label--forest">Следующий шаг</span>
            <h2>{nextItem.title}</h2>
            <p>Отметь пункт выполненным, когда закончишь, — кольцо дня сразу станет полнее.</p>
            <div className="chips">
              <span className="tag">{weekLabel(nextItem.week)}</span>
            </div>
            {upcoming.length > 0 ? (
              <div className="upnext">
                <span className="mono-label">Дальше</span>
                <ol>
                  {upcoming.map((item) => (
                    <li key={item.id}>
                      <span>{item.title}</span>
                      <em>{weekLabel(item.week)}</em>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {checklistQuery.isLoading ? <LoadingLine label="Загружаем чек-лист" /> : null}

      {checklistQuery.isError ? (
        <InlineError
          message={describeError(checklistQuery.error, 'не удалось загрузить чек-лист')}
          onRetry={() => void checklistQuery.refetch()}
        />
      ) : null}

      {!checklistQuery.isLoading && !checklistQuery.isError && items.length === 0 ? (
        <p className="empty">В чек-листе пока нет пунктов.</p>
      ) : null}

      <div className="checklist">
        {groups.map((group) => (
          <div key={group.week} className="checklist__week">
            <h2 className="mono-label">{weekLabel(group.week)}</h2>
            <ul className="tasks">
              {group.items.map((item) => {
                const isDone = item.status === 'done'
                const pendingThisItem =
                  completeMutation.isPending && completeMutation.variables === item.id

                return (
                  <li key={item.id} className={`task ${isDone ? 'is-done' : ''}`}>
                    <button
                      className="task__check"
                      type="button"
                      aria-pressed={isDone}
                      aria-label={`${isDone ? 'Пункт выполнен' : 'Отметить выполненным'}: ${item.title}`}
                      disabled={isDone || pendingThisItem}
                      onClick={() => completeMutation.mutate(item.id)}
                    >
                      {isDone ? <Icon name="check" size={17} /> : null}
                    </button>
                    <div className="task__body">
                      <h3>{item.title}</h3>
                      {item.description ? <p>{item.description}</p> : null}
                    </div>
                    {pendingThisItem ? (
                      <span className="task__meta">
                        <span className="loading-line">Отмечаем</span>
                      </span>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>

      {completeMutation.isError ? (
        <InlineError
          prefix="Ошибка"
          message={describeError(completeMutation.error, 'не удалось отметить пункт')}
          onRetry={() => {
            const id = completeMutation.variables
            if (id) completeMutation.mutate(id)
          }}
        />
      ) : null}
    </section>
  )
}
