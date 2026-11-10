import { useQuery } from '@tanstack/react-query'
import * as api from '../api/client'
import { initials } from '../utils/labels'

export function ContactsList() {
  const contactsQuery = useQuery({
    queryKey: ['contacts'],
    queryFn: api.fetchContacts,
  })

  return (
    <section className="panel" aria-label="Контакты">
      <div className="sec-head sec-head--sm">
        <span className="sec-num">04 —</span>
        <h2 className="sec-title">Контакты</h2>
        <span className="sec-rule" />
      </div>
      <p className="panel__subtitle">Команда адаптации</p>

      {contactsQuery.isLoading ? <p className="panel__placeholder">Загружаем контакты…</p> : null}

      {contactsQuery.isError ? (
        <p className="inline-error" role="alert">
          {contactsQuery.error instanceof Error
            ? contactsQuery.error.message
            : 'Не удалось загрузить контакты.'}
        </p>
      ) : null}

      {contactsQuery.data && contactsQuery.data.length === 0 ? (
        <p className="panel__placeholder">Контакты пока не добавлены.</p>
      ) : null}

      <ul className="contacts">
        {(contactsQuery.data ?? []).map((contact) => (
          <li key={contact.id} className="contacts__item">
            <span className="contacts__avatar" aria-hidden="true">
              {initials(contact.name)}
            </span>
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
