// Made-up rooms and students for previewing the dashboard (VITE_SAMPLE_DATA=true).
// Nothing here comes from the real hostel, and none of it is sent anywhere.
import type { Status } from '../components/ui/status'

export type SampleStudent = { roll: string; name: string; status: Status; note?: string }
export type SampleRoom = { number: string; floor: number; students: SampleStudent[] }

const NAMES = [
  'Asha Verma', 'Rohan Das', 'Priya Nair', 'Kabir Shah', 'Divya Rao', 'Arjun Pillai', 'Meera Iyer', 'Sameer Khan',
  'Tara Bose', 'Nikhil Jain', 'Isha Menon', 'Dev Kapoor', 'Leela George', 'Varun Sethi', 'Anika Roy', 'Farhan Ali',
  'Maya Dutta', 'Kiran Hegde', 'Sana Mirza', 'Aditya Kulkarni', 'Ritu Sharma', 'Naveen Babu', 'Zoya Fernandes', 'Harsh Gill',
]

// Beds that are not simply present, so the sample shows every state.
const EXCEPTIONS: Record<string, { status: Status; note: string }> = {
  '103-2': { status: 'review', note: 'Face match just under the line' },
  '106-0': { status: 'unlit', note: '' },
  '106-1': { status: 'unlit', note: '' },
  '202-3': { status: 'rejected', note: 'Request did not come from the room network' },
  '204-1': { status: 'review', note: 'Room Wi-Fi pattern looked unusual' },
  '205-0': { status: 'unlit', note: '' },
  '301-2': { status: 'unlit', note: '' },
  '303-0': { status: 'rejected', note: 'Signed by a different phone' },
  '305-1': { status: 'unlit', note: '' },
  '305-2': { status: 'unlit', note: '' },
  '305-3': { status: 'review', note: 'Liveness check was borderline' },
}

export const SAMPLE_ROOMS: SampleRoom[] = [3, 2, 1].flatMap((floor) =>
  Array.from({ length: 6 }, (_, r) => {
    const number = `${floor}0${r + 1}`
    const students = Array.from({ length: 4 }, (_, bed): SampleStudent => {
      const seq = (floor - 1) * 24 + r * 4 + bed
      const exception = EXCEPTIONS[`${number}-${bed}`]
      return {
        roll: `TEST${String(seq + 1).padStart(3, '0')}`,
        name: NAMES[seq % NAMES.length],
        status: exception?.status ?? 'present',
        note: exception?.note || undefined,
      }
    })
    return { number, floor, students }
  }),
)

export const SAMPLE_WINDOW = { opens: '22:00', closes: '22:30', state: 'open' as const }

export const SAMPLE_NIGHTS = [
  { night: 'Fri 9 Oct', opens: '22:00', closes: '22:30', present: 70, total: 72, state: 'closed' as const },
  { night: 'Thu 8 Oct', opens: '22:00', closes: '22:45', present: 68, total: 72, state: 'closed' as const },
  { night: 'Wed 7 Oct', opens: '22:00', closes: '22:30', present: 71, total: 72, state: 'closed' as const },
  { night: 'Tue 6 Oct', opens: '', closes: '', present: 0, total: 72, state: 'off' as const },
  { night: 'Mon 5 Oct', opens: '22:00', closes: '22:30', present: 69, total: 72, state: 'closed' as const },
]

export function countByStatus(rooms: SampleRoom[]): Record<Status, number> {
  const counts: Record<Status, number> = { present: 0, review: 0, rejected: 0, unlit: 0 }
  for (const room of rooms) for (const student of room.students) counts[student.status] += 1
  return counts
}

export function studentsWith(rooms: SampleRoom[], status: Status) {
  return rooms.flatMap((room) => room.students.filter((s) => s.status === status).map((s) => ({ ...s, room: room.number })))
}
