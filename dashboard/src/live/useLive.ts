import { useContext } from 'react'
import { LiveContext, type LiveValue } from './context'

export function useLive(): LiveValue {
  const value = useContext(LiveContext)
  if (!value) throw new Error('useLive must be used inside LiveProvider')
  return value
}
