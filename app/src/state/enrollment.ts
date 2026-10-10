/**
 * Enrollment identity, set once at the warden's desk (Phase 6). Secure Store, not
 * AsyncStorage: these values identify the student and are sensitive enough to keep out of
 * plain storage, even though nothing biometric is ever stored on the phone.
 */
import * as SecureStore from 'expo-secure-store';

export type EnrollmentState = 'none' | 'enrolled';

const KEYS = {
  state: 'nightroll.enrollment.state',
  studentId: 'nightroll.enrollment.studentId',
  roomId: 'nightroll.enrollment.roomId',
  roomNumber: 'nightroll.enrollment.roomNumber',
} as const;

export type Enrollment = {
  studentId: string;
  roomId: string;
  roomNumber: string;
};

export async function getEnrollmentState(): Promise<EnrollmentState> {
  const value = await SecureStore.getItemAsync(KEYS.state);
  return value === 'enrolled' ? 'enrolled' : 'none';
}

export async function getEnrollment(): Promise<Enrollment | null> {
  const [studentId, roomId, roomNumber] = await Promise.all([
    SecureStore.getItemAsync(KEYS.studentId),
    SecureStore.getItemAsync(KEYS.roomId),
    SecureStore.getItemAsync(KEYS.roomNumber),
  ]);
  if (!studentId || !roomId || !roomNumber) {
    return null;
  }
  return { studentId, roomId, roomNumber };
}

export async function setEnrollment(enrollment: Enrollment): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(KEYS.studentId, enrollment.studentId),
    SecureStore.setItemAsync(KEYS.roomId, enrollment.roomId),
    SecureStore.setItemAsync(KEYS.roomNumber, enrollment.roomNumber),
    SecureStore.setItemAsync(KEYS.state, 'enrolled'),
  ]);
}

/** Used before re-enrollment: clears identity so the student goes through Welcome again. */
export async function clearEnrollment(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(KEYS.studentId),
    SecureStore.deleteItemAsync(KEYS.roomId),
    SecureStore.deleteItemAsync(KEYS.roomNumber),
    SecureStore.deleteItemAsync(KEYS.state),
  ]);
}
