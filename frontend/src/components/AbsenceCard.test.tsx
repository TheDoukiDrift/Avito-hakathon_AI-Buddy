import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/client'
import type { Absence } from '../api/schemas'
import { AbsenceCard } from './AbsenceCard'

vi.mock('../api/client', () => ({
  fetchAbsences: vi.fn(),
  createAbsence: vi.fn(),
  confirmAbsence: vi.fn(),
}))

const absences: Absence[] = [
  {
    id: '9',
    type: 'day_off',
    date_from: '2026-11-11',
    date_to: '2026-11-11',
    reason: 'Личные дела',
    status: 'approved',
  },
]

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AbsenceCard />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.fetchAbsences).mockReset()
  vi.mocked(api.createAbsence).mockReset()
  vi.mocked(api.confirmAbsence).mockReset()
})

describe('AbsenceCard', () => {
  it('подсказывает бадди, когда заявок нет', async () => {
    vi.mocked(api.fetchAbsences).mockResolvedValue([])
    renderPanel()

    expect(
      await screen.findByText('Заявок пока нет — спросите бадди: «оформи отгул завтра»'),
    ).toBeInTheDocument()
  })

  it('рендерит список заявок со статусом', async () => {
    vi.mocked(api.fetchAbsences).mockResolvedValue(absences)
    renderPanel()

    expect(await screen.findByText(/Отгул · 11 ноября/)).toBeInTheDocument()
    expect(screen.getByText('Согласована')).toBeInTheDocument()
  })

  it('показывает ошибку загрузки и повторяет запрос', async () => {
    vi.mocked(api.fetchAbsences)
      .mockRejectedValueOnce(new Error('Сервис недоступен.'))
      .mockResolvedValueOnce(absences)
    renderPanel()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Ошибка загрузки: Сервис недоступен.')

    fireEvent.click(screen.getByRole('button', { name: 'ПОВТОРИТЬ' }))

    await waitFor(() => expect(api.fetchAbsences).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Согласована')).toBeInTheDocument()
  })
})
