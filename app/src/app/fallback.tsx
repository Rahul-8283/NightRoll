import { useLocalSearchParams } from 'expo-router';
import { StyleSheet } from 'react-native';

import { Button } from '@/components/Button';
import { RoomWindow } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { colors } from '@/theme/colors';

export default function FallbackScreen() {
  const { reason } = useLocalSearchParams<{ reason?: string }>();

  return (
    <Screen glow="ember">
      <RoomWindow light="ember" size={120} label="Your room window, not confirmed" />
      <Eyebrow style={styles.eyebrow}>Not marked from here</Eyebrow>
      <Display>Use the ground-floor scanner</Display>
      <Body style={styles.reason}>
        {reason ?? 'NightRoll could not confirm your attendance from here tonight.'}
      </Body>
      <Body style={styles.centre}>
        Head down and scan at the desk as usual. If the scanner is down, the warden can mark you
        present by hand.
      </Body>
      <Button variant="quiet" label="Back to Home" href="/" />
    </Screen>
  );
}

const styles = StyleSheet.create({
  eyebrow: { color: colors.ember },
  reason: { textAlign: 'center', color: colors.paper },
  centre: { textAlign: 'center' },
});
