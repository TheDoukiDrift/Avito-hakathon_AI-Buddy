import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/client'
import type { ChecklistResponse, Role, User } from '../api/schemas'
import { useAuthStore } from '../stores/authStore'
import { ChecklistPanel } from './ChecklistPanel'

vi.mock('../api/client', () => ({
  getChecklist: vi.fn(),
  completeChecklistItem: vi.fn(),
  getToken: () => null,
  setToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}))

const intern: User = {
  id: '1',
  email: 'intern@example.com',
  role: 'intern',
  full_name: 'Доуки Хоши',
}

const checklist: ChecklistResponse = {
  items: [
    { id: '1', week: 1, title: 'Обсудить цели', description: '', status: 'done' },
    { id: '2', week: 1, title: 'Составить план', description: 'Черновик на неделю', status: 'pending' },
    { id: '3', week: 2, title: 'Запросить доступы', description: '', status: 'pending' },
  ],
  next_item: { id: '2', title: 'Составить план', week: 1 },
  done_count: 1,
  total: 3,
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ChecklistPanel />
    </QueryClientProvider>,
  )
}

function setRole(role: Role) {
  useAuthStore.setState({ user: { ...intern, role } })
}

beforeEach(() => {
  useAuthStore.setState({ user: intern })
  vi.mocked(api.getChecklist).mockReset()
  vi.mocked(api.completeChecklistItem).mockReset()
})

describe('ChecklistPanel', () => {
  it('показывает плашку следующего шага из next_item', async () => {
    vi.mocked(api.getChecklist).mockResolvedValue(checklist)
    renderPanel()

    const plate = await screen.findByLabelText('Следующий шаг')

    expect(plate).toHaveTextContent('Следующий шаг')
    expect(plate).toHaveTextContent('Составить план')
    expect(plate).toHaveTextContent('Неделя 1')
  })

  it('считает прогресс по done_count и total', async () => {
    vi.mocked(api.getChecklist).mockResolvedValue(checklist)
    renderPanel()

    expect(await screen.findByText('33%')).toBeInTheDocument()
    expect(screen.getByText('Выполнено 1 из 3')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '33')
  })

  it('не рисует плашку, когда сервер вернул next_item: null', async () => {
    vi.mocked(api.getChecklist).mockResolvedValue({ ...checklist, next_item: null })
    renderPanel()

    await screen.findByText('Выполнено 1 из 3')

    expect(screen.queryByLabelText('Следующий шаг')).not.toBeInTheDocument()
  })

  it('показывает ошибку загрузки', async () => {
    vi.mocked(api.getChecklist).mockRejectedValue(new Error('Сервис недоступен.'))
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен.')
  })

  it('повторяет загрузку по кнопке «ПОВТОРИТЬ»', async () => {
    vi.mocked(api.getChecklist)
      .mockRejectedValueOnce(new Error('Сервис недоступен.'))
      .mockResolvedValueOnce(checklist)
    renderPanel()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Ошибка загрузки: Сервис недоступен.')

    fireEvent.click(screen.getByRole('button', { name: 'ПОВТОРИТЬ' }))

    await waitFor(() => expect(api.getChecklist).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Выполнено 1 из 3')).toBeInTheDocument()
  })

  it('заменяет плашку следующего шага состоянием «Адаптация пройдена»', async () => {
    const doneChecklist: ChecklistResponse = {
      items: checklist.items.map((item) => ({ ...item, status: 'done' })),
      next_item: null,
      done_count: 3,
      total: 3,
    }
    vi.mocked(api.getChecklist).mockResolvedValue(doneChecklist)
    renderPanel()

    const plate = await screen.findByLabelText('Адаптация пройдена')

    expect(plate).toHaveTextContent('Адаптация пройдена')
    expect(plate).toHaveTextContent('3 из 3')
    expect(plate).toHaveTextContent('спроси бадди')
    expect(screen.queryByLabelText('Следующий шаг')).not.toBeInTheDocument()
  })

  it('блокирует шаг, пока предыдущий не отмечен', async () => {
    vi.mocked(api.getChecklist).mockResolvedValue(checklist)
    renderPanel()

    const firstPending = await screen.findByRole('button', {
      name: 'Отметить выполненным: Составить план',
    })
    const later = screen.getByRole('button', {
      name: 'Отметить выполненным: Запросить доступы',
    })

    expect(firstPending).toBeEnabled()
    expect(later).toBeDisabled()
    expect(later).toHaveAttribute('title', 'Сначала предыдущий шаг')
    expect(screen.getByText('Сначала предыдущий шаг')).toBeInTheDocument()
  })

  it('для наставника показывает прогресс подопечного без отметок', async () => {
    setRole('mentor')
    vi.mocked(api.getChecklist).mockResolvedValue(checklist)
    renderPanel()

    expect(
      await screen.findByRole('heading', { name: 'Прогресс стажёра' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('progressbar', { name: 'Прогресс адаптации подопечного' }),
    ).toBeInTheDocument()
    expect(await screen.findByLabelText('Ближайший шаг подопечного')).toHaveTextContent(
      'Составить план',
    )
    expect(screen.queryByRole('button', { name: /Отметить выполненным/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/спроси бадди/i)).not.toBeInTheDocument()
  })

  it.each(['mentor', 'manager', 'hr_bp'] as const)(
    'в режиме просмотра (%s) плашка не зовёт к бадди',
    async (role) => {
      setRole(role)
      const doneChecklist: ChecklistResponse = {
        items: checklist.items.map((item) => ({ ...item, status: 'done' })),
        next_item: null,
        done_count: 3,
        total: 3,
      }
      vi.mocked(api.getChecklist).mockResolvedValue(doneChecklist)
      renderPanel()

      const plate = await screen.findByLabelText('Подопечный прошёл все шаги')

      expect(plate).toHaveTextContent('Подопечный прошёл все шаги')
      expect(plate).not.toHaveTextContent(/бадди/i)
    },
  )
})
