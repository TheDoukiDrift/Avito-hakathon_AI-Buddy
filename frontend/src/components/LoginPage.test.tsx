import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { LoginPage } from './LoginPage'
import { useAuthStore } from '../stores/authStore'

beforeEach(() => {
  useAuthStore.setState({ token: null, user: null, status: 'anonymous', error: null })
})

describe('LoginPage', () => {
  it('показывает демо-доступы и подсказку по паролю', () => {
    render(<LoginPage />)

    expect(screen.getByRole('heading', { name: 'Вход' })).toBeInTheDocument()
    expect(screen.getByText(/test1234/)).toBeInTheDocument()
    expect(screen.getByText('intern@example.com')).toBeInTheDocument()
    expect(screen.getByText('mentor@example.com')).toBeInTheDocument()
    expect(screen.getByText('manager@example.com')).toBeInTheDocument()
    expect(screen.getByText('hr.bp@example.com')).toBeInTheDocument()
  })

  it('подставляет почту выбранного демо-пользователя', () => {
    render(<LoginPage />)

    fireEvent.click(screen.getByRole('button', { name: /Наставник/ }))

    expect(screen.getByLabelText('Почта')).toHaveValue('mentor@example.com')
  })

  it('показывает ошибку входа', () => {
    useAuthStore.setState({ error: 'Неверный пароль' })
    render(<LoginPage />)

    expect(screen.getByRole('alert')).toHaveTextContent('Неверный пароль')
  })
})
