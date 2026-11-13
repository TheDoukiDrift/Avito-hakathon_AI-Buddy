import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, fetchChatHistory: vi.fn(), streamChat: vi.fn() }
})

import * as api from '../api/client'
import { useChatStore } from '../stores/chatStore'
import { Chat } from './Chat'

const streamChat = vi.mocked(api.streamChat)
const fetchChatHistory = vi.mocked(api.fetchChatHistory)

beforeEach(() => {
  useChatStore.getState().reset()
  streamChat.mockReset()
  fetchChatHistory.mockReset()
  fetchChatHistory.mockResolvedValue([])
})

describe('Chat', () => {
  it('Enter отправляет сообщение', async () => {
    streamChat.mockResolvedValue(undefined)
    render(<Chat />)

    const input = screen.getByLabelText('Сообщение')
    fireEvent.change(input, { target: { value: 'Как оформить отгул?' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => expect(streamChat).toHaveBeenCalledTimes(1))
    expect(streamChat.mock.calls[0]?.[0]).toBe('Как оформить отгул?')
    expect(input).toHaveValue('')
  })

  it('Shift + Enter оставляет перевод строки', async () => {
    render(<Chat />)

    const input = screen.getByLabelText('Сообщение')
    fireEvent.change(input, { target: { value: 'первая строка' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })

    expect(streamChat).not.toHaveBeenCalled()
    expect(input).toHaveValue('первая строка')
  })

  it('сохраняет частичный ответ при обрыве потока и показывает ошибку с повтором', async () => {
    streamChat
      .mockImplementationOnce(async (_message, onToken) => {
        onToken('Начало ответа')
        throw new Error('Обрыв соединения')
      })
      .mockResolvedValueOnce(undefined)
    render(<Chat />)

    const input = screen.getByLabelText('Сообщение')
    fireEvent.change(input, { target: { value: 'Привет' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Ошибка загрузки: Обрыв соединения')
    await waitFor(() => expect(screen.getByText('Начало ответа')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'ПОВТОРИТЬ' }))

    await waitFor(() => expect(streamChat).toHaveBeenCalledTimes(2))
    expect(streamChat.mock.calls[1]?.[0]).toBe('Привет')
    expect(screen.getByText('Начало ответа')).toBeInTheDocument()
  })
})
