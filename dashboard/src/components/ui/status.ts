// The four states a student (one pane of a room window) can be in tonight.
export type Status = 'present' | 'review' | 'rejected' | 'unlit'

export const STATUS_LABEL: Record<Status, string> = {
  present: 'Present',
  review: 'In review',
  rejected: 'Rejected',
  unlit: 'Not yet marked',
}
