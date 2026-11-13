import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => {
  class ApiError extends Error {
    readonly status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  }
  return { ApiError, streamChat: vi.fn(), fetchChatHistory: vi.fn() }
})

import * as api from '../api/client'
import { useChatStore } from './chatStore'

const streamChat = vi.mocked(api.streamChat)

beforeEach(() => {
  useChatStore.getState().reset()
  streamChat.mockReset()
})

describe('chatStore.sendMessage', () => {
  it('добавляет вопрос и накапливает токены ответа', async () => {
    streamChat.mockImplementation(async (_message, onToken) => {
      onToken('Здравствуйте! ')
      onToken('Чем помочь?')
    })

    await useChatStore.getState().sendMessage('  Привет  ')

    const state = useChatStore.getState()
    expect(state.messages.map((message) => message.role)).toEqual(['user', 'assistant'])
    expect(state.messages[0]?.content).toBe('Привет')
    expect(state.messages[1]?.content).toBe('Здравствуйте! Чем помочь?')
    expect(state.sending).toBe(false)
    expect(state.error).toBeNull()
    expect(streamChat).toHaveBeenCalledWith('Привет', expect.any(Function))
  })

  it('показывает fallback-сообщение, если стрим упал', async () => {
    streamChat.mockRejectedValue(new Error('connection reset'))

    await useChatStore.getState().sendMessage('Привет')

    const state = useChatStore.getState()
    expect(state.sending).toBe(false)
    expect(state.error).toBe('connection reset')
    expect(state.messages[1]?.content).toBe('Не удалось получить ответ. Попробуйте ещё раз.')
  })

  it('сохраняет уже полученные токены и не дописывает fallback в текст', async () => {
    streamChat.mockImplementation(async (_message, onToken) => {
      onToken('Начало ответа')
      throw new Error('stream broke')
    })

    await useChatStore.getState().sendMessage('Привет')

    expect(useChatStore.getState().messages[1]?.content).toBe('Начало ответа')
    expect(useChatStore.getState().error).toBe('stream broke')
  })

  it('игнорирует пустой ввод и повторную отправку во время стрима', async () => {
    let finish: () => void = () => undefined
    streamChat.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve
        }),
    )

    await useChatStore.getState().sendMessage('   ')
    expect(streamChat).not.toHaveBeenCalled()

    const first = useChatStore.getState().sendMessage('первое')
    await useChatStore.getState().sendMessage('второе')

    expect(streamChat).toHaveBeenCalledTimes(1)
    expect(useChatStore.getState().sending).toBe(true)

    finish()
    await first
    expect(useChatStore.getState().sending).toBe(false)
  })
})

describe('chatStore.loadHistory', () => {
  it('загружает историю один раз', async () => {
    const history = [
      { id: '1', role: 'user' as const, content: 'привет', created_at: '2026-11-10T10:00:00Z' },
      { id: '2', role: 'assistant' as const, content: 'здравствуйте', created_at: '2026-11-10T10:00:01Z' },
    ]
    const fetchHistory = vi.mocked(api.fetchChatHistory).mockResolvedValue(history)

    await useChatStore.getState().loadHistory()
    await useChatStore.getState().loadHistory()

    expect(fetchHistory).toHaveBeenCalledTimes(1)
    expect(useChatStore.getState().messages).toHaveLength(2)
    expect(useChatStore.getState().historyLoaded).toBe(true)
  })

  it('запоминает ошибку загрузки истории', async () => {
    vi.mocked(api.fetchChatHistory).mockRejectedValue(new Error('backend down'))

    await useChatStore.getState().loadHistory()

    expect(useChatStore.getState().error).toBe('backend down')
    expect(useChatStore.getState().historyLoaded).toBe(false)
  })
})
