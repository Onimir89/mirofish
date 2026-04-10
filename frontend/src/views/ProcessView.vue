<template>
  <div class="view-shell">
    <!-- Top bar -->
    <header class="topbar">
      <router-link to="/" class="topbar-brand">
        <span class="brand-name">MiroFish</span>
        <span class="brand-sep">/</span>
        <span class="brand-context">{{ $t('process.context') }}</span>
      </router-link>
      <div class="topbar-center">
        <div class="view-mode-toggle">
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'graph' }"
            @click="setMode('graph')"
            title="Graph only"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          </button>
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'split' }"
            @click="setMode('split')"
            title="Split view"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="3" x2="12" y2="21"/></svg>
          </button>
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'workbench' }"
            @click="setMode('workbench')"
            title="Workbench only"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          </button>
        </div>
      </div>
      <div class="topbar-status">
        <span class="status-dot" :class="statusClass"></span>
        <span class="status-text">{{ statusLabel }}</span>
      </div>
    </header>

    <!-- Split layout -->
    <div class="split-layout" :class="'mode-' + viewMode">
      <!-- Left: Graph -->
      <div class="panel-left" v-show="isGraphVisible()">
        <GraphPanel
          :graph-data="graphData"
          :loading="graphLoading"
          :current-phase="phase"
        />
      </div>

      <!-- Right: Steps -->
      <div class="panel-right process-panel" v-show="isWorkbenchVisible()">
        <!-- Step 1: Generating Ontology -->
        <div v-if="phase === 'generating'" class="step-card">
          <div class="step-header">
            <div class="step-number">1</div>
            <h2>{{ $t('process.generating_ontology') }}</h2>
          </div>
          <div class="step-body">
            <div class="log-output">
              <div class="log-line" v-for="(line, i) in logLines" :key="i">
                <span class="log-prefix">[{{ formatTime(line.time) }}]</span>
                <span class="log-text">{{ line.text }}</span>
              </div>
              <div class="log-cursor"></div>
            </div>
          </div>
        </div>

        <!-- Step 2: Ontology Review -->
        <div v-if="phase === 'ontology'" class="step-card">
          <div class="step-header">
            <div class="step-number">1</div>
            <h2>{{ $t('process.ontology_generated') }}</h2>
          </div>
          <div class="step-body">
            <div class="ontology-section">
              <h3>{{ $t('process.entity_types') }} <span class="count">({{ ontology.entity_types?.length || 0 }})</span></h3>
              <div class="tag-grid">
                <div
                  v-for="et in ontology.entity_types"
                  :key="et.name"
                  class="tag-item"
                >
                  <span class="tag-name">{{ et.name }}</span>
                  <span class="tag-desc">{{ et.description }}</span>
                </div>
              </div>
            </div>

            <div class="ontology-section">
              <h3>{{ $t('process.edge_types') }} <span class="count">({{ ontology.edge_types?.length || 0 }})</span></h3>
              <div class="tag-grid">
                <div
                  v-for="edge in ontology.edge_types"
                  :key="edge.name"
                  class="tag-item"
                >
                  <span class="tag-name">{{ edge.name }}</span>
                  <span class="tag-desc">{{ edge.source_type }} &rarr; {{ edge.target_type }}</span>
                </div>
              </div>
            </div>

            <button class="btn-accent" :disabled="buildLoading" @click="startBuild">
              <span v-if="buildLoading" class="spinner"></span>
              {{ buildLoading ? $t('process.building') : $t('process.build_graph') }}
            </button>
          </div>
        </div>

        <!-- Step 3: Building Graph -->
        <div v-if="phase === 'building'" class="step-card">
          <div class="step-header">
            <div class="step-number">2</div>
            <h2>{{ $t('process.building_graph') }}</h2>
          </div>
          <div class="step-body">
            <div class="progress-container">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: buildProgress + '%' }"></div>
              </div>
              <span class="progress-pct">{{ buildProgress }}%</span>
            </div>
            <div class="log-output">
              <div class="log-line" v-for="(line, i) in buildLogs" :key="i">
                <span class="log-prefix">[{{ formatTime(line.time) }}]</span>
                <span class="log-text">{{ line.text }}</span>
              </div>
              <div class="log-cursor"></div>
            </div>
          </div>
        </div>

        <!-- Step 4: Graph Ready -->
        <div v-if="phase === 'ready'" class="step-card">
          <div class="step-header">
            <div class="step-number active">&#10003;</div>
            <h2>{{ $t('process.graph_ready') }}</h2>
          </div>
          <div class="step-body">
            <div class="stats-grid">
              <div class="stat-card">
                <span class="stat-value">{{ graphInfo.node_count || 0 }}</span>
                <span class="stat-label">{{ $t('process.entities') }}</span>
              </div>
              <div class="stat-card">
                <span class="stat-value">{{ graphInfo.edge_count || 0 }}</span>
                <span class="stat-label">{{ $t('process.relations') }}</span>
              </div>
              <div class="stat-card">
                <span class="stat-value">{{ ontology.entity_types?.length || 0 }}</span>
                <span class="stat-label">{{ $t('process.entity_types') }}</span>
              </div>
            </div>

            <div v-if="ontology.entity_types" class="ontology-tags">
              <span
                v-for="et in ontology.entity_types"
                :key="et.name"
                class="otag"
              >{{ et.name }}</span>
            </div>

            <button class="btn-accent" @click="enterSimulation">
              {{ $t('process.enter_env_setup') }} &rarr;
            </button>
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="error-card">
          <p>{{ error }}</p>
          <button class="btn-ghost" @click="error = ''">{{ $t('process.dismiss') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '@/components/GraphPanel.vue'
import { generateOntology, buildGraph as apiBuildGraph, getTaskStatus, getGraphData } from '@/api/graph'
import { createSimulation } from '@/api/simulation'
import { getPendingUpload, clearPendingUpload } from '@/store/pendingUpload'
import { useStatus } from '@/composables/useStatus'
import { usePolling } from '@/composables/usePolling'
import { useViewMode } from '@/composables/useViewMode'
import { formatTime } from '@/utils/formatters'

export default {
  name: 'ProcessView',
  components: { GraphPanel },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { viewMode, setMode, isGraphVisible, isWorkbenchVisible } = useViewMode('split')

    const phase = ref('generating')
    const error = ref('')
    const projectId = ref('')
    const ontology = ref({})
    const graphData = ref({ nodes: [], edges: [] })
    const graphLoading = ref(false)
    const graphInfo = ref({})
    const buildLoading = ref(false)
    const buildProgress = ref(0)
    const logLines = ref([])
    const buildLogs = ref([])

    const { statusClass, statusLabel, update: updateStatus } = useStatus('pending', 'Initializing')

    const addLog = (text, target = 'log') => {
      const entry = { time: new Date(), text }
      if (target === 'build') {
        buildLogs.value.push(entry)
      } else {
        logLines.value.push(entry)
      }
    }

    const startProcess = async () => {
      const pid = route.params.projectId

      if (pid === 'new') {
        const pending = getPendingUpload()
        if (!pending.files || !pending.files.length) {
          error.value = 'No files uploaded. Please go back and upload files.'
          phase.value = 'ready'
          return
        }

        updateStatus('active', 'Generating Ontology')
        addLog('Starting ontology generation...')
        addLog(`Processing ${pending.files.length} file(s)...`)

        try {
          const formData = new FormData()
          Array.from(pending.files).forEach((f) => formData.append('files', f))
          formData.append('requirement', pending.requirement || '')
          formData.append('name', 'MiroFish Project')

          const res = await generateOntology(formData)
          projectId.value = res.data.project_id
          ontology.value = res.data.ontology
          addLog(`Ontology generated: ${res.data.ontology.entity_types?.length || 0} entity types, ${res.data.ontology.edge_types?.length || 0} edge types`)
          clearPendingUpload()

          phase.value = 'ontology'
          updateStatus('active', 'Ontology Ready')
        } catch (e) {
          error.value = e.response?.data?.error || e.message
          addLog('ERROR: ' + (e.response?.data?.error || e.message))
          updateStatus('error', 'Failed')
        }
      } else {
        projectId.value = pid
        addLog('Loading existing project...')
        try {
          const { default: apiClient } = await import('@/api/index')
          const res = await apiClient.get(`/api/graph/project/${pid}`)
          const proj = res.data
          ontology.value = proj.ontology || {}

          if (proj.graph_id && proj.status === 'ready') {
            addLog('Graph already built, loading...')
            graphLoading.value = true
            const gRes = await getGraphData(proj.graph_id)
            graphData.value = gRes.data
            graphInfo.value = {
              node_count: gRes.data.nodes?.length || 0,
              edge_count: gRes.data.edges?.length || 0,
            }
            graphLoading.value = false
            phase.value = 'ready'
            updateStatus('success', 'Ready')
          } else if (proj.status === 'building') {
            phase.value = 'building'
            updateStatus('active', 'Building')
          } else {
            phase.value = 'ontology'
            updateStatus('active', 'Ontology Ready')
          }
        } catch (e) {
          error.value = e.response?.data?.error || e.message
          updateStatus('error', 'Failed')
        }
      }
    }

    const currentTaskId = ref(null)

    const taskPoller = usePolling(async () => {
      if (!currentTaskId.value) return
      try {
        const statusRes = await getTaskStatus(currentTaskId.value)
        const task = statusRes.data
        buildProgress.value = task.progress || 0

        if (task.status === 'completed') {
          taskPoller.stop()
          graphPoller.stop()

          graphInfo.value = task.result?.graph_info || {}
          addLog('Graph build completed!', 'build')

          if (task.result?.graph_id) {
            const gRes = await getGraphData(task.result.graph_id)
            graphData.value = gRes.data
            graphInfo.value = {
              node_count: gRes.data.nodes?.length || 0,
              edge_count: gRes.data.edges?.length || 0,
              ...graphInfo.value,
            }
          }

          graphLoading.value = false
          buildLoading.value = false
          phase.value = 'ready'
          updateStatus('success', 'Ready')
        } else if (task.status === 'failed') {
          taskPoller.stop()
          error.value = task.error || 'Build failed'
          addLog('ERROR: ' + (task.error || 'Build failed'), 'build')
          graphLoading.value = false
          buildLoading.value = false
          phase.value = 'ontology'
          updateStatus('error', 'Failed')
        }
      } catch (e) {
        // Polling error - continue trying
      }
    }, 2000)

    const graphPoller = usePolling(async () => {
      try {
        const { default: apiClient } = await import('@/api/index')
        const res = await apiClient.get(`/api/graph/project/${projectId.value}`)
        if (res.data.graph_id) {
          const gRes = await getGraphData(res.data.graph_id)
          graphData.value = gRes.data
        }
      } catch (_) {
        // Ignore polling errors
      }
    }, 10000)

    const startBuild = async () => {
      buildLoading.value = true
      graphLoading.value = true
      error.value = ''
      buildProgress.value = 0
      buildLogs.value = []

      try {
        addLog('Starting graph build...', 'build')
        const res = await apiBuildGraph(projectId.value)
        currentTaskId.value = res.data.task_id

        phase.value = 'building'
        updateStatus('active', 'Building Graph')
        addLog(`Task created: ${currentTaskId.value}`, 'build')

        taskPoller.start()
        graphPoller.start()
      } catch (e) {
        error.value = e.response?.data?.error || e.message
        buildLoading.value = false
        graphLoading.value = false
        updateStatus('error', 'Failed')
      }
    }

    const enterSimulation = async () => {
      try {
        updateStatus('active', 'Creating Simulation')
        const res = await createSimulation(projectId.value)
        const simId = res.data.simulation_id || res.data.id
        router.push(`/simulation/${simId}`)
      } catch (e) {
        error.value = e.response?.data?.error || e.message
      }
    }

    onMounted(() => {
      startProcess()
    })

    return {
      viewMode,
      setMode,
      isGraphVisible,
      isWorkbenchVisible,
      phase,
      error,
      projectId,
      ontology,
      graphData,
      graphLoading,
      graphInfo,
      buildLoading,
      buildProgress,
      logLines,
      buildLogs,
      statusClass,
      statusLabel,
      formatTime,
      startBuild,
      enterSimulation,
    }
  },
}
</script>

<style scoped>
.process-panel {
  width: 420px;
  padding: 1rem;
  overflow-y: auto;
}

/* Ontology tags */
.ontology-section {
  margin-bottom: 1.25rem;
}

.ontology-section h3 {
  font-family: var(--font-heading);
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 0.5rem;
}

.tag-grid {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.tag-item {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.35rem 0;
}

.tag-name {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--accent);
  white-space: nowrap;
}

.tag-desc {
  font-size: 0.75rem;
  color: #666;
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat-card {
  background: #111;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
  text-align: center;
}

.stat-value {
  display: block;
  font-family: var(--font-heading);
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  display: block;
  font-size: 0.7rem;
  color: #666;
  margin-top: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ontology-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 1.25rem;
}

.otag {
  padding: 0.2rem 0.6rem;
  background: rgba(255, 69, 0, 0.1);
  border: 1px solid rgba(255, 69, 0, 0.2);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--accent);
  font-family: var(--font-mono);
}

.log-output {
  margin-bottom: 1rem;
}
</style>
