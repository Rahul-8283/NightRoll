/**
 * "Lights out": the hostel at night, where every room is a window.
 * Lamp = present, moon = in review or scheduled, ember = rejected, unlit = not yet marked.
 * Mirrors dashboard/src/styles/tokens.css. Change a value in both places.
 */
export const colors = {
  ink0: '#07080c',
  ink1: '#0b0d13',
  ink2: '#11141d',
  ink3: '#181c28',
  ink4: '#20253a',
  line: '#262b3c',
  lineSoft: '#1a1e2b',

  paper: '#efe9dd',
  paper2: '#adb2c1',
  paper3: '#7d8397',

  lamp: '#f5b95c',
  lampBright: '#ffd58e',
  lampDeep: '#d98f2b',
  lampWash: 'rgba(245, 185, 92, 0.10)',
  lampGlow: 'rgba(245, 185, 92, 0.34)',
  onLamp: '#1a1204',

  moon: '#a9c1e8',
  moonWash: 'rgba(169, 193, 232, 0.10)',

  ember: '#ee6c4d',
  emberWash: 'rgba(238, 108, 77, 0.12)',
} as const;
