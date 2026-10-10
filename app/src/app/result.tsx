import { StyleSheet } from 'react-native';

import { Button } from '@/components/Button';
import { RoomWindow } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { colors } from '@/theme/colors';

// Sample data: the real verdict and reason arrive from the backend in Phase 7.
const SAMPLE_RESULT = {
  verdict: 'PRESENT' as 'PRESENT' | 'REJECTED',
  reason: 'Face match, room network and device key all checked out.',
};

export default function ResultScreen() {
  const isPresent = SAMPLE_RESULT.verdict === 'PRESENT';

  return (
    <Screen glow={isPresent ? 'lamp' : 'ember'}>
      <RoomWindow
        light={isPresent ? 'lit' : 'ember'}
        label={isPresent ? 'Your room window, lit' : 'Your room window, not confirmed'}
      />
      <Eyebrow style={{ color: isPresent ? colors.lamp : colors.ember }}>Sample result</Eyebrow>
      <Display>{isPresent ? 'You are marked present' : 'Not marked'}</Display>
      <Body style={styles.centre}>{SAMPLE_RESULT.reason}</Body>
      <Body style={styles.note}>The real verdict is connected in Phase 7.</Body>
      {isPresent ? (
        <Button label="Back to Home" href="/" />
      ) : (
        <Button label="What do I do now?" href="/fallback" />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  centre: { textAlign: 'center' },
  note: { textAlign: 'center', fontSize: 14, color: colors.paper3 },
});
