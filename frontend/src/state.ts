// The little state shared between screens: the car, the last dashboard and a toast.

import { ref } from 'vue'
import { api } from './api'
import type { Car, Dashboard } from './types'

export const car = ref<Car | null>(null)
let carLoaded = false

/** Fetch the car once; `null` means it has not been registered yet. */
export async function ensureCar(): Promise<Car | null> {
  if (!carLoaded) {
    car.value = await api.getCar()
    carLoaded = true
  }
  return car.value
}

export function setCar(value: Car): void {
  car.value = value
  carLoaded = true
}

export const dashboard = ref<Dashboard | null>(null)

/** Statuses are recomputed by the server on every request, so always refetch. */
export async function loadDashboard(): Promise<Dashboard> {
  const fresh = await api.getDashboard()
  dashboard.value = fresh
  return fresh
}

export const flash = ref('')
let flashTimer: number | undefined

/** A short confirmation that survives the navigation after a save or delete. */
export function showFlash(message: string): void {
  flash.value = message
  window.clearTimeout(flashTimer)
  flashTimer = window.setTimeout(() => (flash.value = ''), 6000)
}
