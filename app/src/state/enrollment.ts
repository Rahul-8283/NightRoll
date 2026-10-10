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

/**
 * SecureStore has no real web implementation, and some Expo Go builds ship a native module
 * that lags the installed JS package. Either way, this is an automatic check that runs on
 * every app open; it must never crash the screen, so a failure here just means "not
 * enrolled yet" rather than an uncaught error.
 */
async function readItemSafe(key: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
}

export async function getEnrollmentState(): Promise<EnrollmentState> {
  const value = await readItemSafe(KEYS.state);
  return value === 'enrolled' ? 'enrolled' : 'none';
}

export async function getEnrollment(): Promise<Enrollment | null> {
  const [studentId, roomId, roomNumber] = await Promise.all([
    readItemSafe(KEYS.studentId),
    readItemSafe(KEYS.roomId),
    readItemSafe(KEYS.roomNumber),
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
