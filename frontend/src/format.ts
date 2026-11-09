// pt-BR formatting for the values the API sends.

const integer = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const litres = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 2 })
const perLitre = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })

export const fmtInt = (n: number): string => integer.format(n)
export const fmtKm = (n: number): string => `${integer.format(n)} km`
export const fmtYen = (n: number): string => `¥${integer.format(n)}`
export const fmtLitres = (n: number): string => `${litres.format(n)} L`
export const fmtYenPerLitre = (n: number): string => `¥${perLitre.format(n)}/L`

/** `2027-03-20` -> `20/03/2027` */
export function fmtDate(iso: string): string {
  const [year, month, day] = iso.split('-')
  return `${day}/${month}/${year}`
}

/** `2027-03-20` -> `20/03` */
export function fmtDayMonth(iso: string): string {
  const [, month, day] = iso.split('-')
  return `${day}/${month}`
}

function toUtc(iso: string): number {
  const [year, month, day] = iso.split('-').map(Number)
  return Date.UTC(year ?? 0, (month ?? 1) - 1, day ?? 1)
}

/** Whole days from `from` to `to` (both `YYYY-MM-DD`); negative when `to` is earlier. */
export function daysBetween(from: string, to: string): number {
  return Math.round((toUtc(to) - toUtc(from)) / 86_400_000)
}

export function plural(n: number, one: string, many: string): string {
  return Math.abs(n) === 1 ? one : many
}

/** Lower case without accents, for the filter boxes. */
export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}
