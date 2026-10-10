import { StyleSheet, View } from 'react-native';

import { Button } from '@/components/Button';
import { Body, Display, Eyebrow } from '@/components/Text';
import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

type Props = {
  title: string;
  detail: string;
  onCancel?: () => void;
};

/** Shown where the camera would be, in Expo Go and on web, where the native camera does not exist. */
export function CameraUnavailable({ title, detail, onCancel }: Props) {
  return (
    <View style={styles.container}>
      <Eyebrow>Camera</Eyebrow>
      <Display>{title}</Display>
      <Body>{detail}</Body>
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
