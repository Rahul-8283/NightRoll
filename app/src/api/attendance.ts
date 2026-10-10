import { apiFetch } from './client';

/** Mirrors `backend/app/schemas/attendance.py::NonceStatusOut`. */
export type AttendanceStatus =
  | { state: 'open'; window_id: string; nonce: string; closes_at: string; challenge: string[] }
  | { state: 'scheduled'; opens_at: string }
  | { state: 'marked'; window_id: string }
  | { state: 'pending'; window_id: string }
  | { state: 'off' }
  | { state: 'closed' };

export async function fetchAttendanceStatus(studentId: string): Promise<AttendanceStatus> {
  return apiFetch<AttendanceStatus>('/attendance/nonce', { signAs: studentId });
}
