export function rangeFilters(dateField, range) {
  if (!dateField) return []
  const filters = []
  if (range.from)
    filters.push({ field: dateField, operator: 'gte', value: `${range.from}T00:00:00` })
  if (range.to)
    filters.push({ field: dateField, operator: 'lte', value: `${range.to}T23:59:59.999999` })
  return filters
}

export function presetRange(days, now = new Date()) {
  if (!days) return { from: '', to: '' }
  const end = new Date(now)
  const start = new Date(now)
  start.setDate(start.getDate() - days + 1)
  const iso = (date) =>
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  return { from: iso(start), to: iso(end) }
}
