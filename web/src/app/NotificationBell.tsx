/**
 * The bell in the top bar: the person's notifications (GET /notifications), polled every 30
 * seconds (no websockets). Opening it shows the latest; "Mark all read" clears the count.
 */
import { Bell } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { api } from '@/api/client'
import type { NotificationOut } from '@/api/types'
import { fmtBdTime } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function NotificationBell() {
  const t = useT()
  const [items, setItems] = useState<NotificationOut[]>([])
  const [open, setOpen] = useState(false)

  const load = useCallback(() => {
    api<NotificationOut[]>('/notifications').then(setItems, () => undefined)
  }, [])
  useEffect(() => {
    load()
    const id = window.setInterval(load, 30000)
    return () => window.clearInterval(id)
  }, [load])

  const unread = items.filter((n) => !n.read).length
  const readAll = async () => {
    await api('/notifications/read-all', { method: 'POST' }).catch(() => undefined)
    load()
  }

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-label={t(`Notifications, ${unread} unread`, `বিজ্ঞপ্তি, ${unread}টি অপঠিত`)}
        onClick={() => setOpen(!open)}
        className="relative flex size-10 cursor-pointer items-center justify-center rounded-[10px] border border-control-line bg-white text-ink"
      >
        <Bell size={18} aria-hidden="true" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-5 rounded-full bg-[#c63535] px-1 text-center text-[11px] leading-5 font-semibold text-white">{unread}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-[min(92vw,340px)] rounded-card border border-card-line bg-white p-2 shadow-lg">
          <div className="flex items-center justify-between px-2 py-1">
            <strong className="text-[14px] text-ink">{t('Notifications', 'বিজ্ঞপ্তি')}</strong>
            {unread > 0 && (
              <button type="button" className="cursor-pointer border-0 bg-transparent text-[13px] font-semibold text-lens-dark" onClick={() => void readAll()}>
                {t('Mark all read', 'সব পড়া হয়েছে')}
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="m-0 px-2 py-3 text-[13.5px] text-muted-2">{t('Nothing new.', 'নতুন কিছু নেই।')}</p>
          ) : (
            <ul className="m-0 max-h-80 list-none overflow-y-auto p-0">
              {items.map((n) => (
                <li key={n.notification_id} className={`rounded-[8px] px-2 py-2 text-[13.5px] ${n.read ? 'text-body' : 'bg-ground font-semibold text-ink'}`}>
                  {n.link ? (
                    <Link to={n.link} onClick={() => setOpen(false)} className="text-inherit no-underline">
                      {n.text}
                    </Link>
                  ) : (
                    n.text
                  )}
                  <span className="block text-[12px] font-normal text-muted-2">{fmtBdTime(n.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
