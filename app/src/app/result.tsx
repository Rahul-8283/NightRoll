import { useLocalSearchParams } from 'expo-router';
import { useEffect } from 'react';
import { StyleSheet } from 'react-native';

import { Button } from '@/components/Button';
import { RoomWindow } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { formatReason } from '@/marking/reasons';
import { setCachedStatus } from '@/state/statusCache';
import { colors } from '@/theme/colors';

export default function ResultScreen() {
  const params = useLocalSearchParams<{
    verdict?: string;
    reasonCode?: string;
    reasonMessage?: string;
    retryAllowed?: string;
    attemptsLeft?: string;
    markTime?: string;
    windowId?: string;
  }>();

  const verdict = (params.verdict ?? 'PRESENT') as 'PRESENT' | 'NEEDS_REVIEW' | 'REJECTED';
  const retryAllowed = params.retryAllowed !== 'false';
  const markTime = params.markTime ?? 'just now';
  const reasonText = params.reasonMessage || formatReason(params.reasonCode);

  useEffect(() => {
    if (verdict === 'PRESENT' && params.windowId) {
      void setCachedStatus({ state: 'marked', window_id: params.windowId });
    }
  }, [verdict, params.windowId]);

  if (verdict === 'PRESENT') {
    return (
      <Screen glow="lamp">
        <RoomWindow light="lit" label="Your room window, lit" />
        <Eyebrow style={styles.eyebrowLamp}>Confirmed</Eyebrow>
        <Display>You are marked present</Display>
        <Body style={styles.centre}>
          Attendance recorded at {markTime}. All room and device checks passed.
        </Body>
        <Button label="Back to Home" href="/" />
      </Screen>
    );
  }

  if (verdict === 'NEEDS_REVIEW') {
    return (
      <Screen glow="moon">
        <RoomWindow light="waiting" label="Your room window, in review" />
        <Eyebrow style={styles.eyebrowMoon}>Sent to warden</Eyebrow>
        <Display>Sent for warden review</Display>
        <Body style={styles.centre}>{reasonText}</Body>
        <Body style={styles.note}>
          Your mark was forwarded to the warden review queue. You do not need to mark again unless
          requested.
        </Body>
        <Button label="Back to Home" href="/" />
      </Screen>
    );
  }

  // REJECTED
  return (
    <Screen glow="ember">
      <RoomWindow light="ember" label="Your room window, not confirmed" />
      <Eyebrow style={styles.eyebrowEmber}>
        {retryAllowed ? 'Verification failed' : 'No retries left'}
      </Eyebrow>
      <Display>{retryAllowed ? 'Not marked' : 'Marking rejected'}</Display>
      <Body style={styles.centre}>{reasonText}</Body>

      {retryAllowed ? (
        <>
          {params.attemptsLeft && (
            <Body style={styles.note}>{params.attemptsLeft} attempts remaining tonight.</Body>
          )}
          <Button label="Try again" href="/mark" />
          <Button
            variant="quiet"
            label="What do I do now?"
            href={`/fallback?reason=${encodeURIComponent(reasonText)}`}
          />
        </>
      ) : (
        <>
          <Body style={styles.note}>
            You have reached the maximum attempts for tonight. Please mark on the ground-floor
            scanner.
          </Body>
          <Button
            label="Ground-floor scanner directions"
            href={`/fallback?reason=${encodeURIComponent(reasonText)}`}
          />
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  centre: { textAlign: 'center' },
  note: { textAlign: 'center', fontSize: 14, color: colors.paper3 },
  eyebrowLamp: { color: colors.lamp },
  eyebrowMoon: { color: colors.paper2 },
  eyebrowEmber: { color: colors.ember },
});
