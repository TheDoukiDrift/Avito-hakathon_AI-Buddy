import { useState } from 'react'
import { AbsenceCard } from './AbsenceCard'
import { ChecklistPanel } from './ChecklistPanel'
import { ContactsList } from './ContactsList'

type SidebarTab = 'checklist' | 'absence' | 'contacts'

const TABS: Array<{ id: SidebarTab; label: string }> = [
  { id: 'checklist', label: 'Чек-лист' },
  { id: 'absence', label: 'Заявки' },
  { id: 'contacts', label: 'Контакты' },
]

export function Sidebar() {
  const [tab, setTab] = useState<SidebarTab>('checklist')

  return (
    <aside className="sidebar" aria-label="Адаптация">
      <div className="tabs" role="tablist" aria-label="Разделы адаптации">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`tabs__tab ${tab === item.id ? 'tabs__tab--active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="sidebar__panel">
        {tab === 'checklist' ? <ChecklistPanel /> : null}
        {tab === 'absence' ? <AbsenceCard /> : null}
        {tab === 'contacts' ? <ContactsList /> : null}
      </div>
    </aside>
  )
}
