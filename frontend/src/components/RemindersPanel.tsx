import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import { describeError } from '../utils/errors'
import { formatDate, formatTime } from '../utils/labels'
import { Icon } from './Icon'
import { InlineError } from './InlineError'

/**
 * «Напоминания»: что AI-крон оставил пользователю по чек-листу.
 * Пустое состояние не рендерится вовсе — секция появляется только с данными,
 * поэтому пустой блок не занимает место на экране.
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

  // Нет данных — нет секции: пустой блок только шумит.
  // Ошибка загрузки — исключение: её показываем, даже если список пуст.
  if (reminders.length === 0 && !remindersQuery.isError) return null

  return (
    <section className="card card--sand reminders" aria-label="Напоминания">
      <div className="reminders__head">
        <span className="card__icon">
          <Icon name="clock" size={22} />
        </span>
        <div>
          <span className="mono-label">AI-крон · по чек-листу</span>
          <h2>Напоминания</h2>
        </div>
        <span className="tag">{reminders.length}</span>
      </div>

      {remindersQuery.isError ? (
        <InlineError
          message={describeError(remindersQuery.error, 'не удалось загрузить напоминания')}
          onRetry={() => void remindersQuery.refetch()}
        />
      ) : null}

      <ul className="reminders__list">
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
                className="btn btn--sm reminders__ack"
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
