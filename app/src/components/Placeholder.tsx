import { StyleSheet, Text, View } from 'react-native';

type Props = { title: string; phase: string };

// Stand-in for screens whose features are built in later phases.
export function Placeholder({ title, phase }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.note}>Not built yet. Planned in {phase}.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 8 },
  title: { fontSize: 22, fontWeight: '600' },
  note: { fontSize: 15, color: '#59617a', textAlign: 'center' },
});
