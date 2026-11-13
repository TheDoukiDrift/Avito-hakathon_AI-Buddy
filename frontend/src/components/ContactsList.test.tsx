import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/client'
import type { Contact } from '../api/schemas'
import { ContactsList } from './ContactsList'

vi.mock('../api/client', () => ({
  fetchContacts: vi.fn(),
}))

const contacts: Contact[] = [
  { id: '3', name: 'Анна Смирнова', role: 'Наставник', team: 'Core', email: 'a@b.ru' },
]

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ContactsList />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.fetchContacts).mockReset()
})

describe('ContactsList', () => {
  it('рендерит контакты с инициалами и почтой', async () => {
    vi.mocked(api.fetchContacts).mockResolvedValue(contacts)
    renderPanel()

    expect(await screen.findByText('Анна Смирнова')).toBeInTheDocument()
    expect(screen.getByText('АС')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'a@b.ru' })).toHaveAttribute('href', 'mailto:a@b.ru')
  })

  it('показывает ошибку загрузки и повторяет запрос', async () => {
    vi.mocked(api.fetchContacts)
      .mockRejectedValueOnce(new Error('Сервис недоступен.'))
      .mockResolvedValueOnce(contacts)
    renderPanel()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Ошибка загрузки: Сервис недоступен.')

    fireEvent.click(screen.getByRole('button', { name: 'ПОВТОРИТЬ' }))

    await waitFor(() => expect(api.fetchContacts).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Анна Смирнова')).toBeInTheDocument()
  })
})
