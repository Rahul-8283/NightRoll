// Values come from dashboard/.env (VITE_* variables are embedded at build time).
// Only public values belong here: the anon key, never the service role key.
const env = import.meta.env

export const config = {
  apiBaseUrl: env.VITE_API_BASE_URL ?? 'http://localhost:8000/v1',
  wsUrl: env.VITE_WS_URL ?? 'ws://localhost:8000/v1/ws/rooms',
  supabaseUrl: env.VITE_SUPABASE_URL ?? '',
  supabaseAnonKey: env.VITE_SUPABASE_ANON_KEY ?? '',
}

export const missingConfig: string[] = [
  ['VITE_SUPABASE_URL', config.supabaseUrl],
  ['VITE_SUPABASE_ANON_KEY', config.supabaseAnonKey],
]
  .filter(([, value]) => !value)
  .map(([name]) => name)
