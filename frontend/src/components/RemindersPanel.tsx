import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import { describeError } from '../utils/errors'
import { formatDate, formatTime } from '../utils/labels'
import { InlineError } from './InlineError'

/**
 * Секция «05 — НАПОМИНАНИЯ»: что AI-крон оставил пользователю по чек-листу.
 * Пустое состояние не рендерится вовсе — секция появляется только с данными,
 * поэтому пустая вкладка не занимает место на экране.
 */
export function RemindersPanel() {
  const queryClient = useQueryClient()

  const remindersQuery = useQuery({
    queryKey: ['reminders'],
    queryFn: api.getReminders,
  })

  const ackMutation = useMutation({
    mutationFn: api.ackReminder,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reminders'] })
    },
  })

  const reminders = remindersQuery.data ?? []

  // Нет данных — нет секции: пустой блок в сайдбаре только шумит.
  // Ошибка загрузки — исключение: её показываем, даже если список пуст.
  if (reminders.length === 0 && !remindersQuery.isError) return null

  return (
    <section className="panel panel--reminders" aria-label="Напоминания">
      <div className="sec-head sec-head--sm">
        <span className="sec-num">05 —</span>
        <h2 className="sec-title">Напоминания</h2>
        <span className="sec-rule" />
        <span className="panel__percent">{reminders.length}</span>
      </div>

      {remindersQuery.isError ? (
        <InlineError
          message={describeError(remindersQuery.error, 'не удалось загрузить напоминания')}
          onRetry={() => void remindersQuery.refetch()}
        />
      ) : null}

      <ul className="reminders">
        {reminders.map((reminder) => {
          const acking = ackMutation.isPending && ackMutation.variables === reminder.id
          const meta = `${formatDate(reminder.created_at)} · ${formatTime(reminder.created_at)}`

          return (
            <li key={reminder.id} className="reminders__item">
              <div className="reminders__body">
                <p className="reminders__message">{reminder.message}</p>
                <p className="reminders__meta">{meta}</p>
              </div>
              <button
                className="button button--ghost button--small reminders__ack"
                type="button"
                disabled={acking}
                onClick={() => ackMutation.mutate(reminder.id)}
              >
                {acking ? 'Принимаем…' : 'Принял'}
              </button>
            </li>
          )
        })}
      </ul>

      {ackMutation.isError ? (
        <InlineError
          prefix="Ошибка"
          message={describeError(ackMutation.error, 'не удалось подтвердить напоминание')}
          onRetry={() => {
            const id = ackMutation.variables
            if (id) ackMutation.mutate(id)
          }}
        />
      ) : null}
    </section>
  )
}
