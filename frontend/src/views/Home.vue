<template>
  <div class="home">
    <header class="header">
      <h1 class="title">{{ $t('app.title') }}</h1>
      <p class="subtitle">{{ $t('app.subtitle') }}</p>
      <LanguageSwitcher />
    </header>

    <main class="main">
      <!-- Upload Section -->
      <section v-if="step === 'upload'" class="card upload-section">
        <h2>{{ $t('home.upload_title') }}</h2>

        <div
          class="drop-zone"
          :class="{ 'drag-over': isDragging }"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
          @click="$refs.fileInput.click()"
        >
          <div class="drop-icon">+</div>
          <p>{{ $t('home.drop_files') }}</p>
          <p class="hint">{{ $t('home.file_types') }}</p>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".pdf,.md,.txt,.markdown"
            style="display: none"
            @change="handleFileSelect"
          />
        </div>

        <div v-if="selectedFiles.length" class="file-list">
          <div v-for="(file, i) in selectedFiles" :key="i" class="file-item">
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">{{ formatSize(file.size) }}</span>
            <button class="btn-remove" @click="removeFile(i)">&times;</button>
          </div>
        </div>

        <div class="requirement-section">
          <label for="requirement">{{ $t('home.requirement_label') }}</label>
          <textarea
            id="requirement"
            v-model="requirement"
            :placeholder="$t('home.requirement_placeholder')"
            rows="4"
          ></textarea>
        </div>

        <button
          class="btn-primary"
          :disabled="!selectedFiles.length || loading"
          @click="startEngine"
        >
          <span v-if="loading" class="spinner"></span>
          {{ loading ? $t('home.processing') : $t('home.start_engine') }}
        </button>
      </section>

      <!-- Ontology Review -->
      <section v-if="step === 'ontology'" class="card">
        <h2>{{ $t('home.ontology_title') }}</h2>
        <p class="info">{{ $t('common.project') }}: <strong>{{ projectId }}</strong></p>

        <div class="ontology-grid">
          <div class="ontology-col">
            <h3>{{ $t('home.entity_types') }} ({{ ontology.entity_types?.length || 0 }})</h3>
            <ul>
              <li v-for="et in ontology.entity_types" :key="et.name">
                <code>{{ et.name }}</code>
                <span class="desc">{{ et.description }}</span>
              </li>
            </ul>
          </div>
          <div class="ontology-col">
            <h3>{{ $t('home.edge_types') }} ({{ ontology.edge_types?.length || 0 }})</h3>
            <ul>
              <li v-for="edge in ontology.edge_types" :key="edge.name">
                <code>{{ edge.name }}</code>
                <span class="desc">{{ edge.source_type }} -> {{ edge.target_type }}</span>
              </li>
            </ul>
          </div>
        </div>

        <div class="btn-group">
          <button class="btn-secondary" @click="step = 'upload'">{{ $t('common.back') }}</button>
          <button class="btn-primary" :disabled="loading" @click="buildGraph">
            <span v-if="loading" class="spinner"></span>
            {{ loading ? $t('home.building') : $t('home.build_graph') }}
          </button>
        </div>
      </section>

      <!-- Building Progress -->
      <section v-if="step === 'building'" class="card">
        <h2>{{ $t('home.building_title') }}</h2>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <p class="progress-text">{{ progress }}%</p>
      </section>

      <!-- Graph View -->
      <section v-if="step === 'graph'" class="card graph-section">
        <h2>{{ $t('home.graph_title') }}</h2>
        <p class="info">
          {{ graphInfo.node_count }} nodes, {{ graphInfo.edge_count }} edges
        </p>
        <GraphPanel :graph-data="graphData" :loading="building" />
        <button class="btn-secondary" @click="reset">{{ $t('home.new_project') }}</button>
      </section>

      <!-- History Database -->
      <HistoryDatabase />

      <!-- Error -->
      <div v-if="error" class="error-banner">
        {{ error }}
        <button @click="error = ''">&times;</button>
      </div>
    </main>
  </div>
</template>

<script>
import { ref } from 'vue'
import { generateOntology, buildGraph as apiBuildGraph, getTaskStatus, getGraphData } from '@/api/graph'
import GraphPanel from '@/components/GraphPanel.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import HistoryDatabase from '@/components/HistoryDatabase.vue'
import { usePolling } from '@/composables/usePolling'

export default {
  name: 'Home',
  components: { GraphPanel, LanguageSwitcher, HistoryDatabase },
  setup() {
    const step = ref('upload')
    const selectedFiles = ref([])
    const requirement = ref('')
    const loading = ref(false)
    const error = ref('')
    const projectId = ref('')
    const ontology = ref({})
    const progress = ref(0)
    const graphInfo = ref({ node_count: 0, edge_count: 0 })
    const graphData = ref({ nodes: [], edges: [] })
    const building = ref(false)
    const isDragging = ref(false)

    const formatSize = (bytes) => {
      if (bytes < 1024) return bytes + ' B'
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    }

    const handleDrop = (e) => {
      isDragging.value = false
      const files = Array.from(e.dataTransfer.files)
      selectedFiles.value.push(...files)
    }

    const handleFileSelect = (e) => {
      const files = Array.from(e.target.files)
      selectedFiles.value.push(...files)
    }

    const removeFile = (index) => {
      selectedFiles.value.splice(index, 1)
    }

    const startEngine = async () => {
      loading.value = true
      error.value = ''
      try {
        const formData = new FormData()
        selectedFiles.value.forEach((f) => formData.append('files', f))
        formData.append('requirement', requirement.value)
        formData.append('name', 'MiroFish Project')

        const res = await generateOntology(formData)
        projectId.value = res.data.project_id
        ontology.value = res.data.ontology
        step.value = 'ontology'
      } catch (e) {
        error.value = e.response?.data?.error || e.message
      } finally {
        loading.value = false
      }
    }

    let currentTaskId = null

    const { start: startPolling, stop: stopPolling } = usePolling(async () => {
      try {
        const statusRes = await getTaskStatus(currentTaskId)
        const task = statusRes.data
        progress.value = task.progress || 0

        if (task.status === 'completed') {
          stopPolling()
          graphInfo.value = task.result.graph_info || {}
          await loadGraph(task.result.graph_id)
          step.value = 'graph'
          loading.value = false
          building.value = false
        } else if (task.status === 'failed') {
          stopPolling()
          error.value = task.error || 'Build failed'
          step.value = 'ontology'
          loading.value = false
          building.value = false
        }
      } catch (e) {
        stopPolling()
        error.value = e.message
        loading.value = false
        building.value = false
      }
    }, 2000)

    const buildGraphAction = async () => {
      loading.value = true
      building.value = true
      error.value = ''
      try {
        const res = await apiBuildGraph(projectId.value)
        currentTaskId = res.data.task_id
        step.value = 'building'
        progress.value = 0
        startPolling()
      } catch (e) {
        error.value = e.response?.data?.error || e.message
        loading.value = false
        building.value = false
      }
    }

    const loadGraph = async (graphId) => {
      try {
        const res = await getGraphData(graphId)
        graphData.value = res.data
      } catch (e) {
        error.value = 'Failed to load graph: ' + e.message
      }
    }

    const reset = () => {
      step.value = 'upload'
      selectedFiles.value = []
      requirement.value = ''
      projectId.value = ''
      ontology.value = {}
      progress.value = 0
      graphInfo.value = { node_count: 0, edge_count: 0 }
      graphData.value = { nodes: [], edges: [] }
      building.value = false
      error.value = ''
    }

    return {
      step, selectedFiles, requirement, loading, error,
      projectId, ontology, progress, graphInfo, graphData, building,
      isDragging, formatSize, handleDrop, handleFileSelect,
      removeFile, startEngine, buildGraph: buildGraphAction, reset,
    }
  },
}
</script>

<style scoped>
.home {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

.header {
  text-align: center;
  margin-bottom: 2rem;
  position: relative;
}

.title {
  font-family: var(--font-mono);
  font-size: 2.5rem;
  color: var(--accent);
  letter-spacing: 0.1em;
}

.subtitle {
  color: var(--text-secondary);
  margin-top: 0.25rem;
  font-size: 0.9rem;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.card h2 {
  font-family: var(--font-mono);
  color: var(--accent);
  margin-bottom: 1rem;
  font-size: 1.2rem;
}

.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.drop-zone:hover,
.drop-zone.drag-over {
  border-color: var(--accent);
  background: rgba(0, 212, 255, 0.05);
}

.drop-icon {
  font-size: 2rem;
  color: var(--accent-dim);
  margin-bottom: 0.5rem;
}

.hint {
  color: var(--text-secondary);
  font-size: 0.8rem;
  margin-top: 0.5rem;
}

.file-list {
  margin-top: 1rem;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  color: var(--text-primary);
}

.file-size {
  color: var(--text-secondary);
}

.btn-remove {
  background: none;
  border: none;
  color: var(--danger);
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0 0.5rem;
}

.requirement-section {
  margin-top: 1.5rem;
}

.requirement-section label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

textarea {
  width: 100%;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.75rem;
  font-family: var(--font-sans);
  font-size: 0.9rem;
  resize: vertical;
}

textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1.5rem;
  padding: 0.75rem 2rem;
  background: var(--accent);
  color: var(--bg-primary);
  border: none;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.85;
}

.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 0.6rem 1.5rem;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  cursor: pointer;
}

.btn-secondary:hover {
  border-color: var(--text-secondary);
}

.btn-group {
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
}

.info {
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-family: var(--font-mono);
  margin-bottom: 1rem;
}

.ontology-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.ontology-col h3 {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.ontology-col ul {
  list-style: none;
}

.ontology-col li {
  padding: 0.3rem 0;
  font-size: 0.85rem;
}

.ontology-col code {
  color: var(--accent);
  margin-right: 0.5rem;
}

.ontology-col .desc {
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  overflow: hidden;
  margin: 1rem 0;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
  border-radius: 4px;
}

.progress-text {
  text-align: center;
  font-family: var(--font-mono);
  color: var(--accent);
}

.graph-section .btn-secondary {
  margin-top: 1rem;
}

.error-banner {
  position: fixed;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  background: var(--danger);
  color: white;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  z-index: 100;
}

.error-banner button {
  background: none;
  border: none;
  color: white;
  font-size: 1.2rem;
  cursor: pointer;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 600px) {
  .ontology-grid {
    grid-template-columns: 1fr;
  }
}
</style>
