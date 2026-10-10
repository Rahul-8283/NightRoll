import type { RoomUpdate, Totals, TonightData, WindowState } from '../api/types'

const RECENT_LIMIT = 20

function totalsFrom(rooms: TonightData['rooms']): Totals {
  const enrolled = rooms.reduce((sum, room) => sum + room.total, 0)
  const present = rooms.reduce((sum, room) => sum + room.present, 0)
  const pending = rooms.reduce((sum, room) => sum + room.pending_review, 0)
  const rejected = rooms.reduce((sum, room) => sum + room.rejected, 0)
  return {
    enrolled,
    present,
    pending_review: pending,
    not_marked: Math.max(0, enrolled - present - pending),
    rejected,
  }
}

// Once a window has closed, the view stays on its final state (Phase 10 task 4.7).
export function applyRoomUpdate(data: TonightData | undefined, update: RoomUpdate): TonightData | undefined {
  if (!data || data.window?.state === 'closed') return data
  const rooms = data.rooms.map((room) =>
    room.room_id === update.room_id
      ? {
          ...room,
          present: update.present,
          total: update.total,
          pending_review: update.pending_review,
          rejected: update.rejected,
          health: update.health,
        }
      : room,
  )
  const recent = update.last
    ? [update.last, ...data.recent.filter((mark) => mark.mark_id !== update.last?.mark_id)].slice(0, RECENT_LIMIT)
    : data.recent
  return { ...data, rooms, recent, totals: totalsFrom(rooms) }
}

export function applyWindowState(
  data: TonightData | undefined,
  windowId: string,
  state: WindowState,
): TonightData | undefined {
  if (!data?.window || data.window.id !== windowId) return data
  return { ...data, window: { ...data.window, state } }
}
