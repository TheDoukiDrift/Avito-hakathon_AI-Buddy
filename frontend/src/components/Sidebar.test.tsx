import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Role, User } from '../api/schemas'
import { useAuthStore } from '../stores/authStore'
import { Sidebar } from './Sidebar'

vi.mock('./ChecklistPanel', () => ({ ChecklistPanel: () => <div>checklist</div> }))
vi.mock('./RemindersPanel', () => ({ RemindersPanel: () => <div>reminders</div> }))
vi.mock('./AbsenceCard', () => ({ AbsenceCard: () => <div>absences</div> }))
vi.mock('./ContactsList', () => ({ ContactsList: () => <div>contacts</div> }))

const user: User = {
  id: '1',
  email: 'user@example.com',
  role: 'intern',
  full_name: 'Доуки Хоши',
}

function setRole(role: Role) {
  useAuthStore.setState({ user: { ...user, role } })
}

beforeEach(() => {
  setRole('intern')
})

describe('Sidebar', () => {
  it('стажёру показывает напоминания рядом с чек-листом', () => {
    render(<Sidebar section="day" />)

    expect(screen.getByText('checklist')).toBeInTheDocument()
    expect(screen.getByText('reminders')).toBeInTheDocument()
  })

  it.each(['mentor', 'manager', 'hr_bp'] as const)(
    'привилегированной роли (%s) напоминания подопечного не показывает',
    (role) => {
      setRole(role)
      render(<Sidebar section="day" />)

      expect(screen.getByText('checklist')).toBeInTheDocument()
      expect(screen.queryByText('reminders')).not.toBeInTheDocument()
    },
  )
})
