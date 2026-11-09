// Mirrors backend/app/models.py. Dates are always `YYYY-MM-DD` strings.

export type ScheduleType = 'interval' | 'yearly' | 'one_time'
export type Anchor = 'actual' | 'fixed'
export type Status = 'ok' | 'upcoming' | 'due' | 'overdue' | 'no_history' | 'done'
export type TriggerKind = 'km' | 'date' | 'fillups'

export interface Car {
  maker: string
  model: string
  model_code: string
  year: number | null
  plate: string
  tank_l: number | null
  start_km: number
  start_date: string
  shaken_expiry: string | null
  notes: string
}

export interface ScheduleIn {
  id?: string
  type: ScheduleType
  anchor: Anchor
  every_km: number | null
  every_months: number | null
  every_fillups: number | null
  first_due_km: number | null
  first_due_date: string | null
  baseline_km: number | null
  baseline_date: string | null
  months: number[]
  day: number
  at_km: number | null
  on_date: string | null
  lead_km: number | null
  lead_days: number | null
  overdue_km: number | null
  overdue_days: number | null
  active: boolean
}

export interface Schedule extends ScheduleIn {
  id: string
  created_on: string
}

export interface ItemIn {
  name: string
  jp_term: string
  notes: string
  schedules: ScheduleIn[]
}

export interface Item {
  id: string
  name: string
  jp_term: string
  notes: string
  archived: boolean
  schedules: Schedule[]
}

export interface FuelLogIn {
  date: string
  km: number
  litres: number | null
  price_total: number | null
  full_tank: boolean
  fuel_type: string
  station: string
  notes: string
}

export interface FuelLog extends FuelLogIn {
  id: string
}

export interface OdometerIn {
  date: string
  km: number
  note: string
}

export interface OdometerReading extends OdometerIn {
  id: string
}

export interface MaintenanceIn {
  date: string
  km: number
  item_ids: string[]
  cost_total: number | null
  shop: string
  notes: string
}

export interface MaintenanceRecord extends MaintenanceIn {
  id: string
}

export interface ScheduleEvent {
  id: string
  type: 'skip' | 'snooze'
  item_id: string
  schedule_id: string
  date: string
  km: number
  until_km: number | null
  until_date: string | null
  note: string
  created_at: string
}

export interface SkipIn {
  note: string
}

export interface SnoozeIn {
  until_km: number | null
  until_date: string | null
  note: string
}

export interface BaselineIn {
  today?: boolean
  km?: number | null
  date?: string | null
}

export interface TriggerStatus {
  kind: TriggerKind
  status: Status
  /** km, days or fill-ups left until due; negative once past due */
  remaining: number
  due_km: number | null
  due_date: string | null
  due_fillups: number | null
  projected_date: string | null
}

export interface ScheduleStatus {
  item_id: string
  item_name: string
  jp_term: string
  schedule_id: string
  schedule_type: ScheduleType
  status: Status
  raw_status: Status
  triggers: TriggerStatus[]
  driving: TriggerKind | null
  estimated_due_date: string | null
  snoozed: boolean
  snooze_until_km: number | null
  snooze_until_date: string | null
  last_done_date: string | null
  last_done_km: number | null
}

export interface Dashboard {
  today: string
  current_km: number
  last_reading_date: string
  estimated_km: number | null
  pace_km_per_day: number | null
  stale: boolean
  notifications: ScheduleStatus[]
  statuses: ScheduleStatus[]
}

export interface HistoryEntry {
  kind: 'maintenance' | 'skip' | 'snooze'
  id: string
  date: string
  km: number
  item_ids: string[]
  item_names: string[]
  cost_total: number | null
  shop: string
  notes: string
  until_km: number | null
  until_date: string | null
}
