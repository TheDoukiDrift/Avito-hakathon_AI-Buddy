import { create } from 'zustand'
import * as api from '../api/client'
import type { User } from '../api/schemas'

export type AuthStatus = 'idle' | 'authenticating' | 'authenticated' | 'anonymous'

interface AuthState {
  token: string | null
  user: User | null
  status: AuthStatus
  error: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  restore: () => Promise<void>
  clearError: () => void
}

export function errorToMessage(error: unknown): string {
  if (error instanceof api.ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Что-то пошло не так. Попробуйте ещё раз.'
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: api.getToken(),
  user: null,
  status: api.getToken() ? 'idle' : 'anonymous',
  error: null,

  async login(email, password) {
    set({ status: 'authenticating', error: null })
    try {
      const { token, user } = await api.login(email.trim(), password)
      api.setToken(token)
      set({ token, user, status: 'authenticated', error: null })
    } catch (error) {
      set({ status: 'anonymous', error: errorToMessage(error) })
    }
  },

  logout() {
    api.setToken(null)
    set({ token: null, user: null, status: 'anonymous', error: null })
  },

  async restore() {
    const { token } = get()
    if (!token) {
      set({ status: 'anonymous' })
      return
    }
    try {
      const user = await api.fetchMe()
      set({ user, status: 'authenticated' })
    } catch (error) {
      api.setToken(null)
      set({
        token: null,
        user: null,
        status: 'anonymous',
        error: errorToMessage(error),
      })
    }
  },

  clearError() {
    set({ error: null })
  },
}))

// Любой 401 из API-клиента разлогинивает пользователя и возвращает на экран входа.
api.setUnauthorizedHandler(() => {
  useAuthStore.getState().logout()
})
