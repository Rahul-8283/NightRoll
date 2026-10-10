import { StyleSheet, Text, View } from 'react-native';

import { config } from '@/config';

export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>NightRoll</Text>
      <Text style={styles.note}>
        {config.mockStatus
          ? 'Mock status is on. Real window status arrives in Phase 4.'
          : 'Window status is not connected yet. Planned in Phase 4.'}
      </Text>
      <Text style={styles.small}>API: {config.apiBaseUrl}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 8 },
  title: { fontSize: 28, fontWeight: '700' },
  note: { fontSize: 15, color: '#59617a', textAlign: 'center' },
  small: { fontSize: 12, color: '#59617a' },
});
