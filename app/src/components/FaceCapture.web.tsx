// Web build stub. The camera module is native-only, so on web it is never imported (Metro picks this file).
import { StyleSheet, View } from 'react-native';

import { Button } from '@/components/Button';
import { Body, Display, Eyebrow } from '@/components/Text';
import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

export type CapturedFrame = {
  name: string;
  uri: string;
  type: string;
};

type Props = {
  onCaptured: (frames: CapturedFrame[]) => void;
  onCancel?: () => void;
};

export function FaceCapture({ onCancel }: Props) {
  return (
    <View style={styles.container}>
      <Eyebrow>Camera</Eyebrow>
      <Display>Enrollment needs the phone</Display>
      <Body>Face capture only works in the NightRoll Android app. Open it on your phone to enroll.</Body>
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
