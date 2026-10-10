import { apiFetch } from './client';

/** What the warden has settled for tonight, when they have. Mirrors `NonceStatusOut`. */
export type WardenOutcome = {
  outcome?: 'PRESENT' | 'ABSENT' | 'PENDING' | 'NOT_MARKED' | 'OFF';
  decided_how?: 'override' | 'manual' | 'automatic' | 'approved' | 'declined' | null;
};

/** Mirrors `backend/app/schemas/attendance.py::NonceStatusOut`. */
export type AttendanceStatus = WardenOutcome &
  (
    | { state: 'open'; window_id: string; nonce: string; closes_at: string; challenge: string[] }
    | { state: 'scheduled'; opens_at: string }
    | { state: 'marked'; window_id: string }
    | { state: 'absent'; window_id: string }
    | { state: 'pending'; window_id: string }
    | { state: 'off' }
    | { state: 'closed' }
  );

export async function fetchAttendanceStatus(studentId: string): Promise<AttendanceStatus> {
  return apiFetch<AttendanceStatus>('/attendance/nonce', { signAs: studentId });
}
