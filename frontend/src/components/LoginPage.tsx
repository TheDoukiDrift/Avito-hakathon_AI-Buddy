import { useState, type FormEvent } from 'react'
import { useAuthStore } from '../stores/authStore'

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
    <div className="sheet login-sheet">
      <div className="aurora-strip" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>

      {/* Реквизиты титульного листа. */}
      <header className="doc-head">
        <span>
          <b>AI-BUDDY</b> · REV 2026.11 · CASE AVITO · DOC 001
        </span>
        <span className="doc-head__spacer" />
        <span className="coord">
          <b>+57.02°N</b> · 024.06°E
        </span>
        <span>Доступ · терминал 01</span>
      </header>

      <section className="login__intro">
        <h1 className="display">
          AI-<span className="accent">BUDDY</span>
        </h1>
        <p className="lede">
          ИИ-наставник для стажёров: ответы о процессах, чек-лист адаптации и
          организационные действия — в одном месте.
        </p>
        <ul className="login__features">
          <li>Отвечает на вопросы о процессах и инструментах</li>
          <li>Ведёт чек-лист адаптации по неделям</li>
          <li>Помогает оформить отгул или отпуск</li>
          <li>Подсказывает, к кому обратиться</li>
        </ul>
      </section>

      <div className="login__grid">
        <section className="login__col" aria-label="Вход">
          <div className="sec-head">
            <span className="sec-num">01 —</span>
            <h2 className="sec-title">Вход</h2>
            <span className="sec-rule" />
          </div>
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
              <p className="inline-error" role="alert">
                {error}
              </p>
            ) : null}

            <button
              className="button button--primary button--block"
              type="submit"
              disabled={pending}
            >
              {pending ? 'Входим…' : 'Войти'}
            </button>
          </form>
        </section>

        <section className="login__col" aria-label="Демо-доступы">
          <div className="sec-head">
            <span className="sec-num">02 —</span>
            <h2 className="sec-title">Демо-доступы</h2>
            <span className="sec-rule" />
          </div>
          <p className="panel__subtitle">Пароль для всех учётных записей — {DEMO_PASSWORD}</p>

          {/* Реестр учётных записей: строка — кнопка, выноски точками. */}
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

      <footer className="doc-foot">
        <span>
          SYS · <b className="ok">ONLINE</b>
        </span>
        <span className="status-line">
          <span>DOC 001</span>
          <span className="dots" />
          <span>Авторизация</span>
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
