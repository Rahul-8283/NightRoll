// Values come from dashboard/.env (VITE_* variables are embedded at build time).
// Only public values belong here: the anon key, never the service role key.
const env = import.meta.env

// Behind the reverse proxy the dashboard and the API share one address, so VITE_API_BASE_URL and VITE_WS_URL are
// plain paths (/v1, /v1/ws/rooms). A WebSocket needs a full address, so a path is completed from the page's own.
function socketAddress(value: string): string {
  if (!value.startsWith('/')) return value
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${window.location.host}${value}`
}

export const config = {
  apiBaseUrl: env.VITE_API_BASE_URL ?? 'http://localhost:8000/v1',
  wsUrl: socketAddress(env.VITE_WS_URL ?? 'ws://localhost:8000/v1/ws/rooms'),
  supabaseUrl: env.VITE_SUPABASE_URL ?? '',
  supabaseAnonKey: env.VITE_SUPABASE_ANON_KEY ?? '',
}

export const missingConfig: string[] = [
  ['VITE_SUPABASE_URL', config.supabaseUrl],
  ['VITE_SUPABASE_ANON_KEY', config.supabaseAnonKey],
]
  .filter(([, value]) => !value)
  .map(([name]) => name)
