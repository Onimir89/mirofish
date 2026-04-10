/**
 * Format an ISO date string or Date object to locale time (HH:MM:SS).
 * @param {string|Date} dateStr
 * @returns {string}
 */
export function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false })
}
