import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Message } from './Message'
import type { ChatMessage } from '../api/schemas'

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: '1',
    role: 'assistant',
    content: '',
    created_at: '2026-11-11T10:00:00.000Z',
    ...overrides,
  }
}

describe('Message', () => {
  it('рендерит markdown в ответе бадди', () => {
    render(
      <Message
        message={makeMessage({
          content:
            '**Согласуйте дату** с руководителем.\n\n1. Откройте заявку\n2. Укажите период\n\n[Процедура отгула](https://example.com/day-off)',
        })}
      />,
    )

    expect(screen.getByText('Согласуйте дату').tagName).toBe('STRONG')

    const list = screen.getByRole('list')
    expect(list.tagName).toBe('OL')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('Откройте заявку')).toBeInTheDocument()

    const link = screen.getByRole('link', { name: 'Процедура отгула' })
    expect(link).toHaveAttribute('href', 'https://example.com/day-off')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('рендерит маркированный список и инлайн-код', () => {
    render(
      <Message
        message={makeMessage({
          content: '- один\n- два\n\n`GET /api/chat`',
        })}
      />,
    )

    expect(screen.getByRole('list').tagName).toBe('UL')
    expect(screen.getByText('GET /api/chat').tagName).toBe('CODE')
  })

  it('сообщение пользователя остаётся простым текстом', () => {
    render(
      <Message
        message={makeMessage({ role: 'user', content: '**жирный** и [ссылка](https://example.com)' })}
      />,
    )

    expect(document.querySelector('strong')).toBeNull()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(
      screen.getByText('**жирный** и [ссылка](https://example.com)'),
    ).toBeInTheDocument()
  })

  it('переживает потоковый markdown, приходящий кусками', () => {
    const { rerender } = render(
      <Message message={makeMessage({ content: '**Согл' })} streaming />,
    )

    expect(() => rerender(<Message message={makeMessage({ content: '**Согласуйте' })} streaming />)).not.toThrow()

    rerender(
      <Message
        message={makeMessage({
          content: '**Согласуйте дату**\n\n1. Откройте заявку\n\n[Процедура',
        })}
        streaming
      />,
    )

    expect(screen.getByText('Согласуйте дату').tagName).toBe('STRONG')

    rerender(
      <Message
        message={makeMessage({
          content:
            '**Согласуйте дату**\n\n1. Откройте заявку\n\n[Процедура отгула](https://example.com/day-off)',
        })}
      />,
    )

    expect(screen.getByRole('link', { name: 'Процедура отгула' })).toHaveAttribute(
      'href',
      'https://example.com/day-off',
    )
  })

  it('не падает на пустом и незакрытом markdown', () => {
    expect(() =>
      render(<Message message={makeMessage({ content: '```\nне закрыт' })} streaming />),
    ).not.toThrow()
    expect(() => render(<Message message={makeMessage({ content: '' })} streaming />)).not.toThrow()
  })
})
