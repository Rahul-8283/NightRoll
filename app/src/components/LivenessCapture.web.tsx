// Web build stub. The camera module is native-only, so on web it is never imported (Metro picks this file).
import { StyleSheet, View } from 'react-native';

import { Button } from '@/components/Button';
import { Body, Display, Eyebrow } from '@/components/Text';
import type { ChallengeActionType } from '@/modules/face-detector';
import type { ChallengeRecord, FrameRecord } from '@/marking/envelope';
import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

type Props = {
  challengeActions: ChallengeActionType[];
  onComplete: (data: { challenge: ChallengeRecord[]; frames: FrameRecord[] }) => void;
  onCancel?: () => void;
};

export function LivenessCapture({ onCancel }: Props) {
  return (
    <View style={styles.container}>
      <Eyebrow>Check</Eyebrow>
      <Display>Marking needs the phone</Display>
      <Body>The liveness check uses the phone camera. Open NightRoll on your Android phone to mark attendance.</Body>
      {onCancel && <Button label="Back" variant="quiet" onPress={onCancel} />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.ink0,
  },
});
