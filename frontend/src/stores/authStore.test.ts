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
  return {
    ApiError,
    getToken: vi.fn(() => null),
    setToken: vi.fn(),
    login: vi.fn(),
    fetchMe: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
  }
})

import * as api from '../api/client'
import { useAuthStore } from './authStore'

const user = {
  id: '1',
  email: 'intern@example.com',
  role: 'intern' as const,
  full_name: 'Иван Петров',
}

beforeEach(() => {
  vi.clearAllMocks()
  useAuthStore.setState({ token: null, user: null, status: 'anonymous', error: null })
})

describe('authStore.login', () => {
  it('сохраняет токен и пользователя', async () => {
    vi.mocked(api.login).mockResolvedValue({ token: 'jwt-token', user })

    await useAuthStore.getState().login(' intern@example.com ', 'test1234')

    expect(api.login).toHaveBeenCalledWith('intern@example.com', 'test1234')
    expect(api.setToken).toHaveBeenCalledWith('jwt-token')
    expect(useAuthStore.getState()).toMatchObject({
      token: 'jwt-token',
      user,
      status: 'authenticated',
      error: null,
    })
  })

  it('показывает сообщение об ошибке и остаётся на экране входа', async () => {
    vi.mocked(api.login).mockRejectedValue(new api.ApiError(403, 'Неверный пароль'))

    await useAuthStore.getState().login('intern@example.com', 'wrong')

    expect(useAuthStore.getState()).toMatchObject({
      token: null,
      user: null,
      status: 'anonymous',
      error: 'Неверный пароль',
    })
  })
})

describe('authStore.restore', () => {
  it('подтягивает профиль по сохранённому токену', async () => {
    useAuthStore.setState({ token: 'jwt-token' })
    vi.mocked(api.fetchMe).mockResolvedValue(user)

    await useAuthStore.getState().restore()

    expect(useAuthStore.getState()).toMatchObject({ user, status: 'authenticated' })
  })

  it('разлогинивает при истёкшей сессии', async () => {
    useAuthStore.setState({ token: 'jwt-token' })
    vi.mocked(api.fetchMe).mockRejectedValue(new api.ApiError(401, 'Сессия истекла'))

    await useAuthStore.getState().restore()

    expect(api.setToken).toHaveBeenCalledWith(null)
    expect(useAuthStore.getState()).toMatchObject({
      token: null,
      user: null,
      status: 'anonymous',
      error: 'Сессия истекла',
    })
  })

  it('без токена сразу переходит в анонимный режим', async () => {
    await useAuthStore.getState().restore()

    expect(api.fetchMe).not.toHaveBeenCalled()
    expect(useAuthStore.getState().status).toBe('anonymous')
  })
})

describe('authStore.logout', () => {
  it('чистит токен и пользователя', () => {
    useAuthStore.setState({ token: 'jwt-token', user, status: 'authenticated' })

    useAuthStore.getState().logout()

    expect(api.setToken).toHaveBeenCalledWith(null)
    expect(useAuthStore.getState()).toMatchObject({
      token: null,
      user: null,
      status: 'anonymous',
    })
  })
})
