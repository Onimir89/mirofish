import apiClient from './index'

/**
 * Generate a report for a simulation.
 * @param {string} simulationId
 */
export function generateReport(simulationId, projectId = null, graphId = null) {
  const payload = { simulation_id: simulationId }
  if (projectId) payload.project_id = projectId
  if (graphId) payload.graph_id = graphId
  return apiClient.post('/api/report/generate', payload)
}

/**
 * Get report generation status.
 * @param {string} reportId
 */
export function getReportStatus(reportId) {
  return apiClient.get(`/api/report/${reportId}/progress`)
}

/**
 * Get full report.
 * @param {string} reportId
 */
export function getReport(reportId) {
  return apiClient.get(`/api/report/${reportId}`)
}

/**
 * List all reports.
 */
export function listReports() {
  return apiClient.get('/api/report/list')
}

/**
 * Get all report sections.
 * @param {string} reportId
 */
export function getReportSections(reportId) {
  return apiClient.get(`/api/report/${reportId}/sections`)
}

/**
 * Get a specific report section.
 * @param {string} reportId
 * @param {string} sectionId
 */
export function getReportSection(reportId, index) {
  return apiClient.get(`/api/report/${reportId}/section/${index}`)
}

/**
 * Chat with a report (ask questions about the analysis).
 * @param {string} reportId
 * @param {string} message
 * @param {string} agentId - optional specific agent to chat with
 */
export function chatWithReport(reportId, message, agentId = null) {
  const payload = { report_id: reportId, message }
  if (agentId) payload.agent_id = agentId
  return apiClient.post('/api/report/chat', payload)
}
