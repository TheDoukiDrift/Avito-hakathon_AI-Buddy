import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/client'
import type { Reminder } from '../api/schemas'
import { RemindersPanel } from './RemindersPanel'

vi.mock('../api/client', () => ({
  getReminders: vi.fn(),
  ackReminder: vi.fn(),
}))

const reminders: Reminder[] = [
  {
    id: '7',
    checklist_item_id: '2',
    message: 'Не забудьте составить план на неделю',
    created_at: '2026-11-10T10:00:00Z',
  },
  {
    id: '8',
    checklist_item_id: '3',
    message: 'Доступы к репозиторию всё ещё не запрошены',
    created_at: '2026-11-12T09:00:00Z',
  },
]

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <RemindersPanel />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.getReminders).mockReset()
  vi.mocked(api.ackReminder).mockReset()
})

describe('RemindersPanel', () => {
  it('рендерит неподтверждённые напоминания с датой', async () => {
    vi.mocked(api.getReminders).mockResolvedValue(reminders)
    renderPanel()

    expect(await screen.findByText('Не забудьте составить план на неделю')).toBeInTheDocument()
    expect(screen.getByText('Доступы к репозиторию всё ещё не запрошены')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Напоминания' })).toBeInTheDocument()
    expect(screen.getByText('AI-крон · по чек-листу')).toBeInTheDocument()
    expect(screen.getAllByText(/10 ноября/).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Принял' })).toHaveLength(2)
  })

  it('по кнопке «Принял» вызывает ackReminder и обновляет список', async () => {
    vi.mocked(api.getReminders)
      .mockResolvedValueOnce(reminders)
      .mockResolvedValueOnce([reminders[1] as Reminder])
    vi.mocked(api.ackReminder).mockResolvedValue({ id: '7', acked: true })
    renderPanel()

    await screen.findByText('Не забудьте составить план на неделю')
    fireEvent.click(screen.getAllByRole('button', { name: 'Принял' })[0] as HTMLElement)

    await waitFor(() => expect(api.ackReminder).toHaveBeenCalled())
    expect(vi.mocked(api.ackReminder).mock.calls[0]?.[0]).toBe('7')
    await waitFor(() =>
      expect(screen.queryByText('Не забудьте составить план на неделю')).not.toBeInTheDocument(),
    )
    expect(api.getReminders).toHaveBeenCalledTimes(2)
  })

  it('пустое состояние не рендерит секцию вовсе', async () => {
    vi.mocked(api.getReminders).mockResolvedValue([])
    const { container } = renderPanel()

    await waitFor(() => expect(api.getReminders).toHaveBeenCalledTimes(1))

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByLabelText('Напоминания')).not.toBeInTheDocument()
  })

  it('показывает ошибку загрузки', async () => {
    vi.mocked(api.getReminders).mockRejectedValue(new Error('Сервис недоступен.'))
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен.')
  })
})
