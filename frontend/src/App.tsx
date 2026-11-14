import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Chat } from './components/Chat'
import { Icon, type IconName } from './components/Icon'
import { LoginPage } from './components/LoginPage'
import { BrandMark, RingAvatar } from './components/Rings'
import { Sidebar, type WorkspaceSection } from './components/Sidebar'
import { useAuthStore } from './stores/authStore'
import { useChatStore } from './stores/chatStore'
import { initials, roleLabel } from './utils/labels'

const NAV: Array<{ id: WorkspaceSection; label: string; short: string; icon: IconName }> = [
  { id: 'day', label: 'Мой день', short: 'День', icon: 'home' },
  { id: 'absences', label: 'Заявки', short: 'Заявки', icon: 'file' },
  { id: 'contacts', label: 'Контакты', short: 'Контакты', icon: 'people' },
]

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  day: 'Мой день',
  absences: 'Заявки',
  contacts: 'Контакты',
}

export default function App() {
  const queryClient = useQueryClient()

  const token = useAuthStore((state) => state.token)
  const user = useAuthStore((state) => state.user)
  const restore = useAuthStore((state) => state.restore)
  const logout = useAuthStore((state) => state.logout)

  const [section, setSection] = useState<WorkspaceSection>('day')
  const [chatOpen, setChatOpen] = useState(false)

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

  // На узких экранах чат — выдвижная панель: Escape её закрывает.
  useEffect(() => {
    if (!chatOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setChatOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chatOpen])

  if (!token) return <LoginPage />

  if (!user) {
    return (
      <div className="boot">
        <p className="loading-line" role="status">
          Загружаем профиль…
        </p>
      </div>
    )
  }

  const current = SECTION_LABELS[section]

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <BrandMark />
          <div>
            <span className="brand__name">AI-buddy</span>
            <span className="brand__sub">пространство стажёра</span>
          </div>
        </div>

        <div className="me">
          <RingAvatar initials={initials(user.full_name)} />
          <div>
            <strong>{user.full_name}</strong>
            <span>{roleLabel(user.role)}</span>
          </div>
        </div>

        <div className="side__label">Моё пространство</div>
        <nav className="nav" aria-label="Разделы">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={section === item.id ? 'page' : undefined}
              onClick={() => setSection(item.id)}
            >
              <Icon name={item.icon} size={19} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="side__foot">
          <div className="side__note">
            <Icon name="shield" size={18} />
            <span>Доступ только к материалам твоей адаптации</span>
          </div>
          <button className="side__logout" type="button" onClick={logout}>
            <Icon name="x" size={15} /> Выйти
          </button>
          <div className="side__ver">2026.11 · учебные данные</div>
        </div>
      </aside>

      <main className="main">
        <header className="top">
          <div className="crumb">
            <span className="crumb__root">
              Моё пространство <i aria-hidden="true">/</i>
            </span>{' '}
            <b>{current}</b>
          </div>
          <div className="top__right">
            <span className="pill">
              <span className="dot" aria-hidden="true" /> {roleLabel(user.role)}
            </span>
            <button className="btn btn--sm btn--ghost btn-chat" type="button" onClick={() => setChatOpen(true)}>
              <Icon name="chat" size={16} /> Спросить AI-buddy
            </button>
          </div>
        </header>

        <Sidebar section={section} />

        <footer className="foot">
          AI-buddy · демонстрационный интерфейс <span>Профили и данные вымышлены</span>
        </footer>
      </main>

      {chatOpen ? <div className="scrim" onClick={() => setChatOpen(false)} aria-hidden="true" /> : null}
      <Chat open={chatOpen} onClose={() => setChatOpen(false)} />

      <nav className="dock" aria-label="Разделы">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-current={section === item.id ? 'page' : undefined}
            onClick={() => {
              setSection(item.id)
              setChatOpen(false)
            }}
          >
            <Icon name={item.icon} size={21} />
            <span>{item.short}</span>
          </button>
        ))}
        <button type="button" aria-pressed={chatOpen} onClick={() => setChatOpen((open) => !open)}>
          <Icon name="chat" size={21} />
          <span>Чат</span>
        </button>
      </nav>
    </div>
  )
}
