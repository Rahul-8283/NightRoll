// Mirrors backend/app/schemas. Keep these in step with the API.

export type Verdict = 'PRESENT' | 'NEEDS_REVIEW' | 'REJECTED' | 'ABSENT' | 'MANUAL'

export type WindowState = 'scheduled' | 'open' | 'closed' | 'off'

export type WindowBrief = {
  id: string
  night: string
  opens_at: string
  closes_at: string
  state: WindowState
}

export type ReasonOut = { code: string; message: string }

export type RoomCount = {
  room_id: string
  number: string
  floor: number
  present: number
  total: number
  pending_review: number
  rejected: number
}

export type RecentMark = {
  mark_id: string
  verdict: Verdict
  reasons: ReasonOut[]
  marked_at: string
  room_number: string
  student_name: string
  score: number | null
}

export type Totals = {
  enrolled: number
  present: number
  pending_review: number
  not_marked: number
  rejected: number
}

export type TonightData = {
  window: WindowBrief | null
  totals: Totals
  rooms: RoomCount[]
  recent: RecentMark[]
}

export type RoomUpdate = {
  room_id: string
  present: number
  total: number
  pending_review: number
  rejected: number
  last: RecentMark | null
}

export type ScorerOut = { name: string; score: number; reason: string | null; detail: string }

export type MarkDetail = {
  mark_id: string
  verdict: Verdict
  score: number | null
  reasons: ReasonOut[]
  marked_at: string
  attempt: number
  scorers: ScorerOut[]
}

export type RoomStudentStatus = {
  student_id: string
  roll_number: string
  name: string
  active: boolean
  enrolled: boolean
  face_enrolled: boolean
  device_enrolled: boolean
  device_security_level: string | null
  mark: MarkDetail | null
}

export type RoomTonight = {
  room_id: string
  number: string
  floor: number
  window: WindowBrief | null
  students: RoomStudentStatus[]
}

export type WindowHistory = {
  id: string
  night: string
  opens_at: string
  closes_at: string
  state: WindowState
  present: number
  enrolled: number
}

export type RoomRow = { id: string; number: string; floor: number; student_count: number }

export type StudentRow = {
  id: string
  roll_number: string
  name: string
  room_id: string
  room_number: string
  floor: number
  active: boolean
  enrolled: boolean
}

export type EnrollmentStatus = {
  student_id: string
  roll_number: string
  name: string
  room_id: string
  room_number: string
  enrolled: boolean
  enrolled_at: string | null
  consent_at: string | null
  consent_version: string | null
  face_enrolled: boolean
  device_enrolled: boolean
  device_security_level: string | null
  room_fingerprint_enrolled: boolean
  room_fingerprint_version: number | null
}

export type EnrollmentCode = { code: string; student_id: string; expires_at: string }

export type RoomFingerprint = {
  id: string
  room_id: string
  version: number
  pattern: { bssids?: Record<string, unknown>; scans_count?: number }
  ap_count: number
  created_at: string
  age_seconds: number
  reset_pending: boolean
}
