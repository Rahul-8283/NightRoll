// No web platform support: NightRoll is Android only. Any call throws through index.ts,
// since requireOptionalNativeModule('DeviceKey') resolves to null on web with no module here.
export default null;
