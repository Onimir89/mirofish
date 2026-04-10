import apiClient from './index'

/**
 * Generate ontology from uploaded files.
 * @param {FormData} formData - files + requirement + name
 */
export function generateOntology(formData) {
  return apiClient.post('/api/graph/ontology/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/**
 * Start graph building (async).
 * @param {string} projectId
 * @param {object} ontology - optional ontology override
 */
export function buildGraph(projectId, ontology = null) {
  const payload = { project_id: projectId }
  if (ontology) payload.ontology = ontology
  return apiClient.post('/api/graph/build', payload)
}

/**
 * Get task status.
 * @param {string} taskId
 */
export function getTaskStatus(taskId) {
  return apiClient.get(`/api/graph/task/${taskId}`)
}

/**
 * Get graph data for D3 visualization.
 * @param {string} graphId
 */
export function getGraphData(graphId) {
  return apiClient.get(`/api/graph/data/${graphId}`)
}

/**
 * List all projects.
 */
export function listProjects() {
  return apiClient.get('/api/graph/project/list')
}
