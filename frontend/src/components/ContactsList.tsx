import { useQuery } from '@tanstack/react-query'
import * as api from '../api/client'
import { describeError } from '../utils/errors'
import { initials } from '../utils/labels'
import { InlineError } from './InlineError'
import { LoadingLine } from './LoadingLine'
import { RingAvatar } from './Rings'

export function ContactsList() {
  const contactsQuery = useQuery({
    queryKey: ['contacts'],
    queryFn: api.fetchContacts,
  })

  return (
    <section className="panel" aria-label="Контакты">
      <header className="intro">
        <p className="eyebrow">Команда адаптации</p>
        <h1>Контакты</h1>
        <p className="lead">
          Наставник и ответственные за обучение — человеческая поддержка рядом с бадди.
        </p>
      </header>

      {contactsQuery.isLoading ? <LoadingLine label="Загружаем контакты" /> : null}

      {contactsQuery.isError ? (
        <InlineError
          message={describeError(contactsQuery.error, 'не удалось загрузить контакты')}
          onRetry={() => void contactsQuery.refetch()}
        />
      ) : null}

      {contactsQuery.data && contactsQuery.data.length === 0 ? (
        <p className="empty">Контакты пока не добавлены.</p>
      ) : null}

      <ul className="contacts">
        {(contactsQuery.data ?? []).map((contact) => (
          <li key={contact.id} className="contacts__item">
            <RingAvatar initials={initials(contact.name)} />
            <div className="contacts__info">
              <p className="contacts__name">{contact.name}</p>
              <p className="contacts__role">
                {contact.role}
                {contact.team ? ` · ${contact.team}` : ''}
              </p>
              <a className="contacts__email" href={`mailto:${contact.email}`}>
                {contact.email}
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
