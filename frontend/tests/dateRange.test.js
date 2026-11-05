import { test } from 'node:test'
import assert from 'node:assert/strict'
import { presetRange, rangeFilters } from '../src/services/dateRange.js'

test('all-time range does not insert fake boundaries or affect timeless datasets', () => {
  assert.deepEqual(presetRange(0), { from: '', to: '' })
  assert.deepEqual(rangeFilters('date', { from: '', to: '' }), [])
  assert.deepEqual(rangeFilters('', { from: '2026-01-01', to: '2026-02-01' }), [])
})

test('inclusive calendar ranges match the existing API ISO date filters', () => {
  assert.deepEqual(rangeFilters('date', { from: '2026-01-01', to: '2026-01-31' }), [
    { field: 'date', operator: 'gte', value: '2026-01-01T00:00:00' },
    { field: 'date', operator: 'lte', value: '2026-01-31T23:59:59.999999' },
  ])
})

test('open-ended ranges add only the boundary supplied by the user', () => {
  assert.deepEqual(rangeFilters('created_at', { from: '', to: '2026-11-04' }), [
    { field: 'created_at', operator: 'lte', value: '2026-11-04T23:59:59.999999' },
  ])
})

test('presets include today and cross year and leap month boundaries correctly', () => {
  assert.deepEqual(presetRange(7, new Date(2026, 0, 3, 12)), {
    from: '2025-12-28',
    to: '2026-01-03',
  })
  assert.deepEqual(presetRange(30, new Date(2024, 2, 1, 12)), {
    from: '2024-02-01',
    to: '2024-03-01',
  })
})
