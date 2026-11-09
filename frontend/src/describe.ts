// pt-BR wording for what the server computed. No status rule is decided here.

import { daysBetween, fmtDate, fmtDayMonth, fmtInt, fmtKm, plural } from './format'
import type { ScheduleIn, Status, TriggerStatus } from './types'

export const STATUS_LABEL: Record<Status, string> = {
  ok: 'Em dia',
  upcoming: 'Em breve',
  due: 'Vencido',
  overdue: 'Atrasado',
  no_history: 'Sem histórico',
  done: 'Concluído',
}

export const MONTHS = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]

function joinList(parts: string[]): string {
  if (parts.length <= 1) return parts.join('')
  return `${parts.slice(0, -1).join(', ')} e ${parts[parts.length - 1]}`
}

/** "a cada 7.500 km ou 6 meses", "todo ano em maio, dia 31", "uma vez aos 100.000 km" */
export function describeSchedule(s: ScheduleIn): string {
  let text: string
  if (s.type === 'interval') {
    const parts: string[] = []
    if (s.every_fillups) {
      parts.push(
        `${fmtInt(s.every_fillups)} ${plural(s.every_fillups, 'abastecimento', 'abastecimentos')}`,
      )
    }
    if (s.every_km) parts.push(fmtKm(s.every_km))
    if (s.every_months) parts.push(`${s.every_months} ${plural(s.every_months, 'mês', 'meses')}`)
    text = parts.length ? `a cada ${parts.join(' ou ')}` : 'intervalo ainda não definido'
    if (s.anchor === 'fixed') {
      const first: string[] = []
      if (s.first_due_km !== null) first.push(fmtKm(s.first_due_km))
      if (s.first_due_date) first.push(fmtDate(s.first_due_date))
      text += ', datas fixas'
      if (first.length) text += ` (1º vencimento ${first.join(' ou ')})`
    }
  } else if (s.type === 'yearly') {
    const names = s.months.map((m) => MONTHS[m - 1] ?? String(m))
    text = names.length ? `todo ano em ${joinList(names)}, dia ${s.day}` : 'todo ano, meses ainda não definidos'
  } else {
    const parts: string[] = []
    if (s.at_km !== null) parts.push(`aos ${fmtKm(s.at_km)}`)
    if (s.on_date) parts.push(`em ${fmtDate(s.on_date)}`)
    text = parts.length ? `uma vez ${parts.join(' ou ')}` : 'uma vez, km ou data ainda não definidos'
  }
  return s.active ? text : `${text} (inativa)`
}

/** "faltam 400 km", "vence hoje", "vencido há 1 abastecimento" */
export function triggerReason(t: TriggerStatus): string {
  const n = Math.abs(t.remaining)
  const left = n === 1 ? 'falta' : 'faltam'
  if (t.kind === 'km') {
    if (t.remaining > 0) return `${left} ${fmtKm(n)}`
    return t.remaining === 0 ? 'vence agora' : `vencido há ${fmtKm(n)}`
  }
  if (t.kind === 'date') {
    const unit = `${fmtInt(n)} ${plural(n, 'dia', 'dias')}`
    if (t.remaining > 0) return `${left} ${unit}`
    return t.remaining === 0 ? 'vence hoje' : `vencido há ${unit}`
  }
  const unit = `${fmtInt(n)} ${plural(n, 'abastecimento', 'abastecimentos')}`
  if (t.remaining > 0) return `${left} ${unit}`
  return t.remaining === 0 ? 'vence agora' : `vencido há ${unit}`
}

/** Where the trigger's due point is: "aos 96.350 km" or "20/03/2027". */
export function triggerDue(t: TriggerStatus): string {
  if (t.kind === 'km' && t.due_km !== null) return `aos ${fmtKm(t.due_km)}`
  if (t.kind === 'date' && t.due_date) return fmtDate(t.due_date)
  return ''
}

function roughly(days: number): string {
  if (days <= 0) return '~hoje'
  if (days < 14) return `~${days} ${plural(days, 'dia', 'dias')}`
  if (days < 60) return `~${Math.round(days / 7)} semanas`
  if (days < 730) return `~${Math.round(days / 30)} meses`
  return `~${Math.round(days / 365)} anos`
}

/** For a km trigger with a projected date: "~3 semanas (30/11)". */
export function projection(t: TriggerStatus, today: string): string {
  if (t.kind !== 'km' || !t.projected_date) return ''
  const sameYear = t.projected_date.slice(0, 4) === today.slice(0, 4)
  const when = sameYear ? fmtDayMonth(t.projected_date) : fmtDate(t.projected_date)
  return `${roughly(daysBetween(today, t.projected_date))} (${when})`
}
