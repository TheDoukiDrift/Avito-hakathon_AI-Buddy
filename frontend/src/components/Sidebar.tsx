import { useState } from 'react'
import { AbsenceCard } from './AbsenceCard'
import { ChecklistPanel } from './ChecklistPanel'
import { ContactsList } from './ContactsList'
import { RemindersPanel } from './RemindersPanel'

type SidebarTab = 'checklist' | 'absence' | 'contacts'

const TABS: Array<{ id: SidebarTab; label: string }> = [
  { id: 'checklist', label: 'Чек-лист' },
  { id: 'absence', label: 'Заявки' },
  { id: 'contacts', label: 'Контакты' },
]

export function Sidebar() {
  const [tab, setTab] = useState<SidebarTab>('checklist')

  return (
    <aside className="sidebar" aria-label="Адаптация" data-tab={tab}>
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

      {/* Все панели смонтированы: на смартфоне они идут подряд, без вкладок. */}
      <div className="sidebar__panel">
        <div className="sidebar__pane" data-pane="checklist">
          <ChecklistPanel />
          <RemindersPanel />
        </div>
        <div className="sidebar__pane" data-pane="absence">
          <AbsenceCard />
        </div>
        <div className="sidebar__pane" data-pane="contacts">
          <ContactsList />
        </div>
      </div>
    </aside>
  )
}
