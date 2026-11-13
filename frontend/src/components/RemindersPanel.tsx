import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import { formatDate, formatTime } from '../utils/labels'

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
  const loadError =
    remindersQuery.error instanceof Error
      ? remindersQuery.error.message
      : remindersQuery.isError
        ? 'Не удалось загрузить напоминания.'
        : null

  // Нет данных — нет секции: пустой блок в сайдбаре только шумит.
  if (reminders.length === 0 && !loadError) return null

  return (
    <section className="panel panel--reminders" aria-label="Напоминания">
      <div className="sec-head sec-head--sm">
        <span className="sec-num">05 —</span>
        <h2 className="sec-title">Напоминания</h2>
        <span className="sec-rule" />
        <span className="panel__percent">{reminders.length}</span>
      </div>

      {loadError ? (
        <p className="inline-error" role="alert">
          {loadError}
        </p>
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
        <p className="inline-error" role="alert">
          {ackMutation.error instanceof Error
            ? ackMutation.error.message
            : 'Не удалось подтвердить напоминание.'}
        </p>
      ) : null}
    </section>
  )
}
