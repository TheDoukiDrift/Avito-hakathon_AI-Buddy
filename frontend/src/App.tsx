import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Chat } from './components/Chat'
import { LoginPage } from './components/LoginPage'
import { Sidebar } from './components/Sidebar'
import { useAuthStore } from './stores/authStore'
import { useChatStore } from './stores/chatStore'
import { roleLabel } from './utils/labels'

export default function App() {
  const queryClient = useQueryClient()

  const token = useAuthStore((state) => state.token)
  const user = useAuthStore((state) => state.user)
  const restore = useAuthStore((state) => state.restore)
  const logout = useAuthStore((state) => state.logout)

  const previousUserId = useRef<string | undefined>(undefined)

  useEffect(() => {
    void restore()
  }, [restore])

  // При смене пользователя (или выходе) чистим кэш запросов и историю чата,
  // чтобы данные одной роли не утекли в интерфейс другой.
  const userId = user?.id
  useEffect(() => {
    if (previousUserId.current !== undefined && previousUserId.current !== userId) {
      useChatStore.getState().reset()
      queryClient.clear()
    }
    previousUserId.current = userId
  }, [userId, queryClient])

  if (!token) return <LoginPage />

  if (!user) {
    return (
      <div className="boot">
        <span className="blink" aria-hidden="true">
          ▋
        </span>
        <p>Загружаем профиль…</p>
      </div>
    )
  }

  return (
    <div className="sheet sheet--app">
      <div className="aurora-strip" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>

      {/* Реквизиты документа: проект, ревизия, кейс, номер формы. */}
      <header className="doc-head">
        <span>
          <b>AI-BUDDY</b> · REV 2026.11
          <span className="doc-head__tail"> · CASE AVITO · DOC 001</span>
        </span>
        <span className="doc-head__spacer" />
        <span className="doc-head__user">
          {user.full_name} · {roleLabel(user.role)}
        </span>
        <button className="button button--ghost button--small" type="button" onClick={logout}>
          Выйти
        </button>
      </header>

      <main className="workspace">
        <Chat />
        <Sidebar />
      </main>

      {/* Колонтитул: статус сессии и курсор. */}
      <footer className="doc-foot">
        <span>
          SYS · <b className="ok">ONLINE</b>
        </span>
        <span className="status-line">
          <span>{roleLabel(user.role)}</span>
          <span className="dots" />
          <span>DOC 001</span>
        </span>
        <span>
          2026.11{' '}
          <span className="blink" aria-hidden="true">
            ▋
          </span>
        </span>
      </footer>
    </div>
  )
}
