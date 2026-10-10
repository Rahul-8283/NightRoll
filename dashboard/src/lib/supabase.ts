import { createClient } from '@supabase/supabase-js'
import { config } from '../config'

// Used for warden login only. Attendance data is always read through the NightRoll API.
export const supabase = createClient(config.supabaseUrl || 'http://localhost', config.supabaseAnonKey || 'missing')
