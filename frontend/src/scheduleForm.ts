// Editable shape of a schedule, and its conversion to the API payload.

import type { Anchor, Schedule, ScheduleIn, ScheduleType } from './types'

export interface ScheduleForm {
  /** Local key for the list; the server id (if any) is in `id`. */
  key: number
  id: string | null
  type: ScheduleType
  anchor: Anchor
  every_km: number | null
  every_months: number | null
  every_fillups: number | null
  first_due_km: number | null
  first_due_date: string
  baseline_km: number | null
  baseline_date: string
  months: number[]
  day: number | null
  at_km: number | null
  on_date: string
  lead_km: number | null
  lead_days: number | null
  overdue_km: number | null
  overdue_days: number | null
  active: boolean
}

let nextKey = 1

export function newScheduleForm(): ScheduleForm {
  return {
    key: nextKey++,
    id: null,
    type: 'interval',
    anchor: 'actual',
    every_km: null,
    every_months: null,
    every_fillups: null,
    first_due_km: null,
    first_due_date: '',
    baseline_km: null,
    baseline_date: '',
    months: [],
    day: 1,
    at_km: null,
    on_date: '',
    lead_km: null,
    lead_days: null,
    overdue_km: null,
    overdue_days: null,
    active: true,
  }
}

export function toScheduleForm(s: Schedule): ScheduleForm {
  return {
    key: nextKey++,
    id: s.id,
    type: s.type,
    anchor: s.anchor,
    every_km: s.every_km,
    every_months: s.every_months,
    every_fillups: s.every_fillups,
    first_due_km: s.first_due_km,
    first_due_date: s.first_due_date ?? '',
    baseline_km: s.baseline_km,
    baseline_date: s.baseline_date ?? '',
    months: [...s.months],
    day: s.day,
    at_km: s.at_km,
    on_date: s.on_date ?? '',
    lead_km: s.lead_km,
    lead_days: s.lead_days,
    overdue_km: s.overdue_km,
    overdue_days: s.overdue_days,
    active: s.active,
  }
}

/** Which "última vez" fields an interval schedule counting from the last time uses. */
export function baselineNeeds(s: {
  every_km: number | null
  every_months: number | null
  every_fillups: number | null
}): { km: boolean; date: boolean } {
  return { km: !!s.every_km, date: !!s.every_months || !!s.every_fillups }
}

/**
 * Only the fields of the chosen type are sent; the rest go as `null` so a
 * schedule that changed type does not keep values the form no longer shows.
 */
export function toSchedulePayload(f: ScheduleForm): ScheduleIn {
  const interval = f.type === 'interval'
  const fixed = interval && f.anchor === 'fixed'
  const actual = interval && f.anchor === 'actual'
  const yearly = f.type === 'yearly'
  const oneTime = f.type === 'one_time'

  const payload: ScheduleIn = {
    type: f.type,
    anchor: f.anchor,
    every_km: interval ? f.every_km : null,
    every_months: interval ? f.every_months : null,
    every_fillups: actual ? f.every_fillups : null,
    first_due_km: fixed ? f.first_due_km : null,
    first_due_date: fixed ? f.first_due_date || null : null,
    baseline_km: actual ? f.baseline_km : null,
    baseline_date: actual ? f.baseline_date || null : null,
    months: yearly ? [...f.months].sort((a, b) => a - b) : [],
    day: yearly ? (f.day ?? 1) : 1,
    at_km: oneTime ? f.at_km : null,
    on_date: oneTime ? f.on_date || null : null,
    lead_km: f.lead_km,
    lead_days: f.lead_days,
    overdue_km: f.overdue_km,
    overdue_days: f.overdue_days,
    active: f.active,
  }
  if (f.id) payload.id = f.id
  return payload
}
