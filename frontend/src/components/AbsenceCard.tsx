import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'
import type { Absence, AbsenceType } from '../api/schemas'
import {
  absenceStatusMeta,
  absenceTypeLabel,
  formatDateRange,
  todayIso,
} from '../utils/labels'
import { describeError } from '../utils/errors'
import { InlineError } from './InlineError'
import { LoadingLine } from './LoadingLine'

const ABSENCE_TYPES: AbsenceType[] = ['day_off', 'vacation', 'sick']

export function AbsenceCard() {
  const queryClient = useQueryClient()

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
  }

  const draftStatus = draft ? absenceStatusMeta(draft.status) : null
  const isDraft = draft?.status === 'draft'

  return (
    <section className="panel" aria-label="Заявка на отсутствие">
      <div className="sec-head sec-head--sm">
        <span className="sec-num">03 —</span>
        <h2 className="sec-title">Заявки</h2>
        <span className="sec-rule" />
      </div>
      <p className="panel__subtitle">Отгул, отпуск или больничный</p>

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
            className="button button--primary button--block"
            type="submit"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Готовим черновик…' : 'Создать черновик'}
          </button>
        </form>
      ) : (
        <div className="absence-draft">
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
                Проверьте детали. После подтверждения заявка уйдёт руководителю, затем HR BP.
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
              <div className="absence-draft__actions">
                <button
                  className="button button--primary"
                  type="button"
                  disabled={confirmMutation.isPending}
                  onClick={() => confirmMutation.mutate(draft.id)}
                >
                  {confirmMutation.isPending ? 'Отправляем…' : 'Подтвердить и отправить'}
                </button>
                <button className="button button--ghost" type="button" onClick={startNew}>
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
              <div className="absence-draft__actions">
                <button className="button button--ghost" type="button" onClick={startNew}>
                  Новая заявка
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <div className="absence-list">
        <h3 className="absence-list__title">Мои заявки</h3>
        {absencesQuery.isLoading ? <LoadingLine label="Загружаем заявки" /> : null}
        {absencesQuery.isError ? (
          <InlineError
            message={describeError(absencesQuery.error, 'не удалось загрузить заявки')}
            onRetry={() => void absencesQuery.refetch()}
          />
        ) : null}
        {absencesQuery.data && absencesQuery.data.length === 0 ? (
          <p className="panel__placeholder">
            Заявок пока нет — спросите бадди: «оформи отгул завтра»
          </p>
        ) : null}
        <ul className="absence-list__items">
          {(absencesQuery.data ?? []).map((absence) => {
            const meta = absenceStatusMeta(absence.status)
            return (
              <li key={absence.id} className="absence-list__item">
                <div>
                  <p className="absence-list__type">
                    {absenceTypeLabel(absence.type)} · {formatDateRange(absence.date_from, absence.date_to)}
                  </p>
                  {absence.reason ? <p className="absence-list__reason">{absence.reason}</p> : null}
                </div>
                <span className={`badge badge--${meta.tone}`}>{meta.label}</span>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
