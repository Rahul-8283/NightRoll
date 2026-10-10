import type { Href } from 'expo-router';

import { Button } from '@/components/Button';
import { RoomWindow } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Eyebrow, Title } from '@/components/Text';

type Props = {
  title: string;
  phase: string;
  /** Shown as a "Continue" button, so the real flow stays navigable while this is a shell. */
  nextRoute?: Href;
  nextLabel?: string;
};

// Stand-in for screens whose features are built in later phases.
export function Placeholder({ title, phase, nextRoute, nextLabel = 'Continue' }: Props) {
  return (
    <Screen glow="moon">
      <RoomWindow light="dark" size={96} label="An unlit window" />
      <Eyebrow>Not built yet</Eyebrow>
      <Title style={{ textAlign: 'center' }}>{title}</Title>
      <Body style={{ textAlign: 'center' }}>Planned in {phase}.</Body>
      {nextRoute && <Button variant="quiet" label={nextLabel} href={nextRoute} />}
    </Screen>
  );
}
