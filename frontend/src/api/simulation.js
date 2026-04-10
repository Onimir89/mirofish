import apiClient from './index'

/**
 * Create a new simulation for a project.
 * @param {string} projectId
 * @param {object} config - optional simulation config overrides
 */
export function createSimulation(projectId, config = {}) {
  return apiClient.post('/api/simulation/create', { project_id: projectId, ...config })
}

/**
 * Prepare simulation (generate profiles, config).
 * @param {string} simulationId
 */
export function prepareSimulation(simulationId) {
  return apiClient.post('/api/simulation/prepare', { simulation_id: simulationId })
}

/**
 * Get preparation task status.
 * @param {string} simulationId
 */
export function getPrepareStatus(simulationId) {
  return apiClient.post('/api/simulation/prepare/status', { simulation_id: simulationId })
}

/**
 * Get simulation details.
 * @param {string} simulationId
 */
export function getSimulation(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}`)
}

/**
 * List all simulations.
 */
export function listSimulations() {
  return apiClient.get('/api/simulation/list')
}

/**
 * Start a simulation run.
 * @param {string} simulationId
 * @param {object} options - { rounds, platforms }
 */
export function startSimulation(simulationId, options = {}) {
  return apiClient.post('/api/simulation/start', { simulation_id: simulationId, ...options })
}

/**
 * Stop a running simulation.
 * @param {string} simulationId
 */
export function stopSimulation(simulationId) {
  return apiClient.post('/api/simulation/stop', { simulation_id: simulationId })
}

/**
 * Get run status (summary).
 * @param {string} simulationId
 */
export function getRunStatus(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * Get detailed run status per platform.
 * @param {string} simulationId
 */
export function getRunStatusDetail(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * Get simulation actions (timeline).
 * @param {string} simulationId
 * @param {object} params - { limit, offset, agent, platform, action_type }
 */
export function getSimulationActions(simulationId, params = {}) {
  return apiClient.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * Get simulation timeline.
 * @param {string} simulationId
 */
export function getSimulationTimeline(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}/timeline`)
}

/**
 * Get per-agent statistics.
 * @param {string} simulationId
 */
export function getAgentStats(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * Get agent profiles for a simulation.
 * @param {string} simulationId
 */
export function getSimulationProfiles(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}/profiles`)
}

/**
 * Get simulation config.
 * @param {string} simulationId
 */
export function getSimulationConfig(simulationId) {
  return apiClient.get(`/api/simulation/${simulationId}/config`)
}

/**
 * Get simulation history (past projects).
 * @param {number} limit - max entries to return
 */
export function getSimulationHistory(limit = 20) {
  return apiClient.get(`/api/simulation/history?limit=${limit}`)
}
