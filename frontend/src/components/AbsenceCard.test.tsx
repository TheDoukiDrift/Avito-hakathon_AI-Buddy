import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/client'
import type { Absence, User } from '../api/schemas'
import { useAuthStore } from '../stores/authStore'
import { AbsenceCard } from './AbsenceCard'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    fetchAbsences: vi.fn(),
    createAbsence: vi.fn(),
    confirmAbsence: vi.fn(),
    approveAbsence: vi.fn(),
    rejectAbsence: vi.fn(),
  }
})

const absences: Absence[] = [
  {
    id: '9',
    user_id: '1',
    type: 'day_off',
    date_from: '2026-11-11',
    date_to: '2026-11-11',
    reason: 'Личные дела',
    status: 'approved',
  },
]

/** Чужая заявка на согласовании: у неё и появляются кнопки решения. */
const pending: Absence = {
  id: '11',
  user_id: '1',
  type: 'vacation',
  date_from: '2026-11-20',
  date_to: '2026-11-22',
  reason: 'Отпуск',
  status: 'pending_approval',
}

const intern: User = {
  id: '1',
  email: 'intern@example.com',
  role: 'intern',
  full_name: 'Иван Петров',
}

const mentor: User = {
  id: '2',
  email: 'mentor@example.com',
  role: 'mentor',
  full_name: 'Мария Смирнова',
}

function signIn(user: User | null) {
  useAuthStore.setState({ user, token: user ? 'jwt-token' : null })
}

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
  vi.mocked(api.approveAbsence).mockReset()
  vi.mocked(api.rejectAbsence).mockReset()
  signIn(null)
})

afterEach(() => {
  signIn(null)
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

describe('AbsenceCard · решение по заявке', () => {
  it('стажёр не видит кнопок согласования', async () => {
    signIn(intern)
    vi.mocked(api.fetchAbsences).mockResolvedValue([pending])
    renderPanel()

    expect(await screen.findByText(/Отпуск · 20 ноября/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Согласовать/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Отклонить/ })).not.toBeInTheDocument()
  })

  it('наставник видит кнопки для чужой заявки', async () => {
    signIn(mentor)
    vi.mocked(api.fetchAbsences).mockResolvedValue([pending])
    renderPanel()

    expect(await screen.findByRole('button', { name: /Согласовать/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Отклонить/ })).toBeInTheDocument()
  })

  it('не предлагает согласовать собственную заявку', async () => {
    signIn(mentor)
    vi.mocked(api.fetchAbsences).mockResolvedValue([{ ...pending, user_id: mentor.id }])
    renderPanel()

    expect(await screen.findByText(/Отпуск · 20 ноября/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Согласовать/ })).not.toBeInTheDocument()
  })

  it('«Согласовать» вызывает approve и показывает новый статус', async () => {
    signIn(mentor)
    vi.mocked(api.fetchAbsences)
      .mockResolvedValueOnce([pending])
      .mockResolvedValue([{ ...pending, status: 'approved' }])
    vi.mocked(api.approveAbsence).mockResolvedValue({ id: '11', status: 'approved' })
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: /Согласовать/ }))

    await waitFor(() => expect(api.approveAbsence).toHaveBeenCalledWith('11'))
    expect(await screen.findByText('Согласована')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Согласовать/ })).not.toBeInTheDocument()
  })

  it('«Отклонить» вызывает reject', async () => {
    signIn(mentor)
    vi.mocked(api.fetchAbsences)
      .mockResolvedValueOnce([pending])
      .mockResolvedValue([{ ...pending, status: 'rejected' }])
    vi.mocked(api.rejectAbsence).mockResolvedValue({ id: '11', status: 'rejected' })
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: /Отклонить/ }))

    await waitFor(() => expect(api.rejectAbsence).toHaveBeenCalledWith('11'))
    expect(await screen.findByText('Отклонена')).toBeInTheDocument()
  })

  it('показывает причину отказа 403 и не прячет интерфейс', async () => {
    signIn(mentor)
    vi.mocked(api.fetchAbsences).mockResolvedValue([pending])
    vi.mocked(api.approveAbsence).mockRejectedValue(
      new Error('Недостаточно прав для этого действия'),
    )
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: /Согласовать/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ошибка: Недостаточно прав для этого действия',
    )
    expect(screen.getByRole('button', { name: /Отклонить/ })).toBeInTheDocument()
  })
})
