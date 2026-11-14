import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import type { Absence, AbsenceType, Role } from '../api/schemas'
import { useAuthStore } from '../stores/authStore'
import {
  absenceStatusMeta,
  absenceTypeLabel,
  formatDateRange,
  todayIso,
} from '../utils/labels'
import { describeError } from '../utils/errors'
import { Icon } from './Icon'
import { InlineError } from './InlineError'
import { LoadingLine } from './LoadingLine'

const ABSENCE_TYPES: AbsenceType[] = ['day_off', 'vacation', 'sick']

/** Кто вправе согласовать чужую заявку (RBAC бэкенда: mentor/manager/hr_bp). */
const DECIDER_ROLES: Role[] = ['mentor', 'manager', 'hr_bp']

type Decision = 'approve' | 'reject'

interface DecisionInput {
  id: string
  action: Decision
}

/**
 * Кнопки решения показываем только там, где бэкенд точно их примет:
 * согласующая роль, статус «на согласовании», заявка не своя.
 * Без user_id в ответе (старый контракт) решать не берёмся.
 */
function canDecide(role: Role | undefined, userId: string | undefined, absence: Absence): boolean {
  if (!role || !DECIDER_ROLES.includes(role)) return false
  if (absence.status !== 'pending_approval') return false
  if (absence.user_id === undefined) return false
  return absence.user_id !== userId
}

export function AbsenceCard() {
  const queryClient = useQueryClient()
  const user = useAuthStore((state) => state.user)

  const [type, setType] = useState<AbsenceType>('day_off')
  const [dateFrom, setDateFrom] = useState(todayIso())
  const [dateTo, setDateTo] = useState(todayIso())
  const [reason, setReason] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [draft, setDraft] = useState<Absence | null>(null)

  const absencesQuery = useQuery({
    queryKey: ['absences'],
    queryFn: api.fetchAbsences,
  })

  const createMutation = useMutation({
    mutationFn: api.createAbsence,
    onSuccess: (response) => {
      setDraft({
        id: response.id,
        type: response.type ?? type,
        date_from: response.date_from ?? dateFrom,
        date_to: response.date_to ?? dateTo,
        reason: response.reason ?? reason.trim(),
        status: response.status,
      })
      setFormError(null)
    },
  })

  const confirmMutation = useMutation({
    mutationFn: api.confirmAbsence,
    onSuccess: (update) => {
      setDraft((current) => (current ? { ...current, status: update.status } : current))
      void queryClient.invalidateQueries({ queryKey: ['absences'] })
    },
  })

  const decisionMutation = useMutation({
    mutationFn: ({ id, action }: DecisionInput) =>
      action === 'approve' ? api.approveAbsence(id) : api.rejectAbsence(id),
    onSuccess: (update) => {
      // Строка меняет статус сразу; кэш всё равно сверяем с сервером.
      queryClient.setQueryData<Absence[]>(['absences'], (current) =>
        current
          ? current.map((item) => (item.id === update.id ? { ...item, status: update.status } : item))
          : current,
      )
      void queryClient.invalidateQueries({ queryKey: ['absences'] })
    },
  })

  const submitDraft = () => {
    if (!dateFrom || !dateTo) {
      setFormError('Укажите дату начала и окончания.')
      return
    }
    if (dateTo < dateFrom) {
      setFormError('Дата окончания не может быть раньше даты начала.')
      return
    }
    setFormError(null)
    createMutation.mutate({
      type,
      date_from: dateFrom,
      date_to: dateTo,
      reason: reason.trim(),
    })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    submitDraft()
  }

  const startNew = () => {
    setDraft(null)
    setReason('')
    setFormError(null)
    createMutation.reset()
    confirmMutation.reset()
    decisionMutation.reset()
  }

  const draftStatus = draft ? absenceStatusMeta(draft.status) : null
  const isDraft = draft?.status === 'draft'
  const decidingId = decisionMutation.isPending ? decisionMutation.variables?.id : undefined

  return (
    <section className="panel" aria-label="Заявка на отсутствие">
      <header className="intro">
        <p className="eyebrow">Организационные действия</p>
        <h1>Заявки</h1>
        <p className="lead">
          Отгул, отпуск или больничный: черновик, затем согласование руководителя и HR BP.
        </p>
      </header>

      {!draft ? (
        <form className="absence-form" onSubmit={handleSubmit}>
          <label className="field">
            <span className="field__label">Тип</span>
            <select
              className="field__input"
              value={type}
              onChange={(event) => setType(event.target.value as AbsenceType)}
            >
              {ABSENCE_TYPES.map((absenceType) => (
                <option key={absenceType} value={absenceType}>
                  {absenceTypeLabel(absenceType)}
                </option>
              ))}
            </select>
          </label>

          <div className="absence-form__dates">
            <label className="field">
              <span className="field__label">С</span>
              <input
                className="field__input"
                type="date"
                value={dateFrom}
                onChange={(event) => {
                  const value = event.target.value
                  setDateFrom(value)
                  if (!dateTo || dateTo < value) setDateTo(value)
                }}
                required
              />
            </label>
            <label className="field">
              <span className="field__label">По</span>
              <input
                className="field__input"
                type="date"
                value={dateTo}
                min={dateFrom}
                onChange={(event) => setDateTo(event.target.value)}
                required
              />
            </label>
          </div>

          <label className="field">
            <span className="field__label">Причина</span>
            <textarea
              className="field__input field__input--textarea"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Например: личные дела во второй половине дня"
              rows={2}
            />
          </label>

          {formError ? (
            <p className="inline-error inline-error--static" role="alert">
              {formError}
            </p>
          ) : null}

          {createMutation.isError ? (
            <InlineError
              prefix="Ошибка"
              message={describeError(createMutation.error, 'не удалось создать черновик заявки')}
              onRetry={submitDraft}
            />
          ) : null}

          <button
            className="btn btn--primary btn--block"
            type="submit"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Готовим черновик…' : 'Создать черновик'}
          </button>
        </form>
      ) : (
        <div className="card card--paper absence-draft">
          <div className="absence-draft__row">
            <span className="absence-draft__label">Тип</span>
            <span>{absenceTypeLabel(draft.type)}</span>
          </div>
          <div className="absence-draft__row">
            <span className="absence-draft__label">Даты</span>
            <span>{formatDateRange(draft.date_from, draft.date_to)}</span>
          </div>
          {draft.reason ? (
            <div className="absence-draft__row">
              <span className="absence-draft__label">Причина</span>
              <span>{draft.reason}</span>
            </div>
          ) : null}
          <div className="absence-draft__row">
            <span className="absence-draft__label">Статус</span>
            {draftStatus ? (
              <span className={`badge badge--${draftStatus.tone}`}>{draftStatus.label}</span>
            ) : null}
          </div>

          {isDraft ? (
            <>
              <p className="absence-draft__note">
                Проверь детали. После подтверждения заявка уйдёт руководителю, затем HR BP.
              </p>
              {confirmMutation.isError ? (
                <InlineError
                  prefix="Ошибка"
                  message={describeError(confirmMutation.error, 'не удалось отправить заявку')}
                  onRetry={() => {
                    if (draft) confirmMutation.mutate(draft.id)
                  }}
                />
              ) : null}
              <div className="actions">
                <button
                  className="btn btn--primary"
                  type="button"
                  disabled={confirmMutation.isPending}
                  onClick={() => confirmMutation.mutate(draft.id)}
                >
                  {confirmMutation.isPending ? 'Отправляем…' : 'Подтвердить и отправить'}
                </button>
                <button className="btn btn--ghost" type="button" onClick={startNew}>
                  Отменить
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="absence-draft__note">
                {draft.status === 'pending_approval'
                  ? 'Заявка отправлена: сначала согласует руководитель, затем HR BP.'
                  : 'Статус заявки обновлён.'}
              </p>
              <div className="actions">
                <button className="btn btn--ghost" type="button" onClick={startNew}>
                  Новая заявка
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <div className="absence-list">
        <h2 className="mono-label">Мои заявки</h2>
        {absencesQuery.isLoading ? <LoadingLine label="Загружаем заявки" /> : null}
        {absencesQuery.isError ? (
          <InlineError
            message={describeError(absencesQuery.error, 'не удалось загрузить заявки')}
            onRetry={() => void absencesQuery.refetch()}
          />
        ) : null}
        {absencesQuery.data && absencesQuery.data.length === 0 ? (
          <p className="empty">Заявок пока нет — спросите бадди: «оформи отгул завтра»</p>
        ) : null}

        <ul className="tasks">
          {(absencesQuery.data ?? []).map((absence) => {
            const meta = absenceStatusMeta(absence.status)
            const decidable = canDecide(user?.role, user?.id, absence)
            const busy = decidingId === absence.id

            return (
              <li key={absence.id} className="task task--absence">
                <div className="task__body">
                  <h3>
                    {absenceTypeLabel(absence.type)} · {formatDateRange(absence.date_from, absence.date_to)}
                  </h3>
                  {absence.reason ? <p>{absence.reason}</p> : null}
                  <div className="task__meta">
                    <span className={`badge badge--${meta.tone}`}>{meta.label}</span>
                  </div>

                  {decidable ? (
                    <div className="actions absence-decision">
                      <button
                        className="btn btn--sm btn--approve"
                        type="button"
                        disabled={busy}
                        onClick={() => decisionMutation.mutate({ id: absence.id, action: 'approve' })}
                      >
                        <Icon name="check" size={16} /> Согласовать
                      </button>
                      <button
                        className="btn btn--sm btn--reject"
                        type="button"
                        disabled={busy}
                        onClick={() => decisionMutation.mutate({ id: absence.id, action: 'reject' })}
                      >
                        <Icon name="x" size={16} /> Отклонить
                      </button>
                    </div>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>

        {decisionMutation.isError ? (
          <InlineError
            prefix="Ошибка"
            message={describeError(decisionMutation.error, 'не удалось изменить статус заявки')}
            onRetry={() => {
              const input = decisionMutation.variables
              if (input) decisionMutation.mutate(input)
            }}
          />
        ) : null}
      </div>
    </section>
  )
}
