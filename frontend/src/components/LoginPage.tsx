import { useState, type FormEvent } from 'react'
import { useAuthStore } from '../stores/authStore'
import { BrandMark } from './Rings'

const DEMO_PASSWORD = 'test1234'

const DEMO_ACCOUNTS = [
  { email: 'intern@example.com', label: 'Стажёр' },
  { email: 'mentor@example.com', label: 'Наставник' },
  { email: 'manager@example.com', label: 'Руководитель' },
  { email: 'hr.bp@example.com', label: 'HR BP' },
] as const

export function LoginPage() {
  const login = useAuthStore((state) => state.login)
  const status = useAuthStore((state) => state.status)
  const error = useAuthStore((state) => state.error)
  const clearError = useAuthStore((state) => state.clearError)

  const [email, setEmail] = useState('intern@example.com')
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const pending = status === 'authenticating'

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (pending) return
    void login(email, password)
  }

  const pickAccount = (demoEmail: string) => {
    clearError()
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
  }

  return (
    <div className="login">
      <div className="login__inner">
        <header className="login__intro">
          <div className="brand brand--login">
            <BrandMark />
            <div>
              <span className="brand__name">AI-buddy</span>
              <span className="brand__sub">пространство стажёра</span>
            </div>
          </div>

          <p className="eyebrow">Адаптация стажёра</p>
          <h1 className="display">
            Каждый день добавляет <span className="accent">кольцо</span>
          </h1>
          <p className="lead">
            ИИ-наставник для стажёров: ответы о процессах, чек-лист адаптации и
            организационные действия — в одном месте.
          </p>
          <ul className="login__features">
            <li>Отвечает на вопросы о процессах и инструментах</li>
            <li>Ведёт чек-лист адаптации по неделям</li>
            <li>Помогает оформить отгул или отпуск</li>
            <li>Подсказывает, к кому обратиться</li>
          </ul>
        </header>

        <div className="login__grid">
          <section className="card card--paper login__card" aria-label="Вход">
            <h2>Вход</h2>
            <p className="panel__subtitle">Корпоративная почта и пароль</p>

            <form className="login__form" onSubmit={handleSubmit}>
              <label className="field">
                <span className="field__label">Почта</span>
                <input
                  className="field__input"
                  type="email"
                  name="email"
                  autoComplete="username"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value)
                    if (error) clearError()
                  }}
                  required
                />
              </label>

              <label className="field">
                <span className="field__label">Пароль</span>
                <input
                  className="field__input"
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value)
                    if (error) clearError()
                  }}
                  required
                />
              </label>

              {error ? (
                <p className="inline-error inline-error--static" role="alert">
                  {error}
                </p>
              ) : null}

              <button className="btn btn--primary btn--block" type="submit" disabled={pending}>
                {pending ? 'Входим…' : 'Войти'}
              </button>
            </form>
          </section>

          <section className="card card--sand login__card" aria-label="Демо-доступы">
            <h2>Демо-доступы</h2>
            <p className="panel__subtitle">Пароль для всех учётных записей — {DEMO_PASSWORD}</p>

            {/* Реестр учётных записей: строка — кнопка. */}
            <div className="reg">
              <div className="reg__head" aria-hidden="true">
                <span>Логин</span>
                <span />
                <span>Роль</span>
              </div>
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  className={`reg__row ${email === account.email ? 'reg__row--active' : ''}`}
                  onClick={() => pickAccount(account.email)}
                >
                  <span className="reg__email">{account.email}</span>
                  <span className="reg__dots" aria-hidden="true" />
                  <span className="reg__role">{account.label}</span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <footer className="foot foot--login">
          AI-buddy · демонстрационный интерфейс <span>Профили и данные вымышлены</span>
        </footer>
      </div>
    </div>
  )
}
