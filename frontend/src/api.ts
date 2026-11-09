// Typed client for the back end. Every rule lives there; this file only talks HTTP.

import type {
  BaselineIn,
  Car,
  Dashboard,
  FuelLog,
  FuelLogIn,
  HistoryEntry,
  Item,
  ItemIn,
  MaintenanceIn,
  MaintenanceRecord,
  OdometerIn,
  OdometerReading,
  ScheduleEvent,
  SkipIn,
  SnoozeIn,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** The pt-BR message to show for anything thrown by an API call. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Algo deu errado. Tente de novo.'
}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Não foi possível conectar ao servidor.', 0)
  }
  if (!response.ok) {
    let detail: unknown
    try {
      detail = ((await response.json()) as { detail?: unknown } | null)?.detail
    } catch {
      // no JSON body (for example the dev proxy when the API is down)
    }
    throw new ApiError(
      typeof detail === 'string' && detail
        ? detail
        : `O servidor respondeu com erro (${response.status}).`,
      response.status,
    )
  }
  return response
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const schedulePath = (itemId: string, scheduleId: string) =>
  `/items/${itemId}/schedules/${scheduleId}`

export const api = {
  getCar: () => request<Car | null>('GET', '/car'),
  putCar: (car: Car) => request<Car>('PUT', '/car', car),
  getDashboard: () => request<Dashboard>('GET', '/dashboard'),

  listItems: (includeArchived = false) =>
    request<Item[]>('GET', includeArchived ? '/items?include_archived=true' : '/items'),
  getItem: (id: string) => request<Item>('GET', `/items/${id}`),
  createItem: (body: ItemIn) => request<Item>('POST', '/items', body),
  updateItem: (id: string, body: ItemIn) => request<Item>('PUT', `/items/${id}`, body),
  deleteItem: (id: string) => request<{ archived: boolean }>('DELETE', `/items/${id}`),
  restoreItem: (id: string) => request<Item>('POST', `/items/${id}/restore`),

  skip: (itemId: string, scheduleId: string, body: SkipIn) =>
    request<ScheduleEvent>('POST', `${schedulePath(itemId, scheduleId)}/skip`, body),
  snooze: (itemId: string, scheduleId: string, body: SnoozeIn) =>
    request<ScheduleEvent>('POST', `${schedulePath(itemId, scheduleId)}/snooze`, body),
  setBaseline: (itemId: string, scheduleId: string, body: BaselineIn) =>
    request<Item>('POST', `${schedulePath(itemId, scheduleId)}/baseline`, body),
  deleteEvent: (id: string) => request<void>('DELETE', `/events/${id}`),

  listFuel: () => request<FuelLog[]>('GET', '/fuel'),
  createFuel: (body: FuelLogIn) => request<FuelLog>('POST', '/fuel', body),
  updateFuel: (id: string, body: FuelLogIn) => request<FuelLog>('PUT', `/fuel/${id}`, body),
  deleteFuel: (id: string) => request<void>('DELETE', `/fuel/${id}`),

  listOdometer: () => request<OdometerReading[]>('GET', '/odometer'),
  createOdometer: (body: OdometerIn) => request<OdometerReading>('POST', '/odometer', body),
  deleteOdometer: (id: string) => request<void>('DELETE', `/odometer/${id}`),

  listMaintenance: () => request<MaintenanceRecord[]>('GET', '/maintenance'),
  createMaintenance: (body: MaintenanceIn) =>
    request<MaintenanceRecord>('POST', '/maintenance', body),
  updateMaintenance: (id: string, body: MaintenanceIn) =>
    request<MaintenanceRecord>('PUT', `/maintenance/${id}`, body),
  deleteMaintenance: (id: string) => request<void>('DELETE', `/maintenance/${id}`),

  getHistory: () => request<HistoryEntry[]>('GET', '/history'),

  /** The export document exactly as the server sent it, for the download. */
  getExportText: async () => (await send('GET', '/export')).text(),
}
