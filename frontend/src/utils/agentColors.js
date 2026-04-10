const AGENT_COLORS = [
  '#FF6B35', '#004E89', '#7B2D8E', '#2E8B57', '#DC143C',
  '#FF8C00', '#4169E1', '#8B4513', '#008B8B', '#9932CC',
]

/**
 * Deterministic color for an agent name based on hash.
 * @param {string} name
 * @returns {string} hex color
 */
export function getAgentColor(name) {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length]
}
