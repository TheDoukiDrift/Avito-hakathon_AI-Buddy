import { AbsenceCard } from './AbsenceCard'
import { ChecklistPanel } from './ChecklistPanel'
import { ContactsList } from './ContactsList'
import { RemindersPanel } from './RemindersPanel'

export type WorkspaceSection = 'day' | 'absences' | 'contacts'

interface SidebarProps {
  /** Раздел «Моего пространства», выбранный в навигации (см. NAV в App). */
  section: WorkspaceSection
}

/**
 * Содержимое рабочего пространства: раньше это были вкладки сайдбара, теперь —
 * страницы, которые переключает навигация (как в дизайн-системе «Годовые
 * кольца»: слева навигация, в центре страница, справа чат).
 */
export function Sidebar({ section }: SidebarProps) {
  return (
    <div className="page">
      {section === 'day' ? (
        <>
          <ChecklistPanel />
          <RemindersPanel />
        </>
      ) : null}
      {section === 'absences' ? <AbsenceCard /> : null}
      {section === 'contacts' ? <ContactsList /> : null}
    </div>
  )
}
