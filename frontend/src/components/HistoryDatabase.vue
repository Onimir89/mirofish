<template>
  <section class="history-database">
    <div class="history-header">
      <h2 class="history-title">History Database</h2>
      <div class="history-border"></div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="history-loading">
      <span class="spinner"></span>
      <span>Loading history...</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="!simulations.length" class="history-empty">
      <div class="empty-icon">&#x25CB;</div>
      <p>No simulations yet</p>
      <p class="empty-hint">Upload documents and run a simulation to see it here.</p>
    </div>

    <!-- Cards grid -->
    <div v-else class="history-grid">
      <div
        v-for="sim in simulations"
        :key="sim.id"
        class="history-card"
        @click="openModal(sim)"
      >
        <div class="card-top">
          <span class="sim-id" :title="sim.id">{{ truncateId(sim.id) }}</span>
          <span class="status-badge" :class="statusClass(sim.status)">
            {{ sim.status }}
          </span>
        </div>

        <p class="card-requirement">{{ truncateText(sim.requirement, 80) }}</p>

        <div class="card-files" v-if="sim.files && sim.files.length">
          <span v-for="f in sim.files.slice(0, 3)" :key="f" class="file-tag">{{ f }}</span>
          <span v-if="sim.files.length > 3" class="file-tag file-tag-more">+{{ sim.files.length - 3 }}</span>
        </div>

        <div class="card-bottom">
          <span class="card-rounds">{{ sim.current_round || 0 }}/{{ sim.total_rounds || 0 }} rounds</span>
          <span class="card-date">{{ formatDate(sim.created_at) }}</span>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <Teleport to="body">
      <div v-if="selectedSim" class="modal-overlay" @click.self="closeModal">
        <div class="modal-content">
          <button class="modal-close" @click="closeModal">&times;</button>

          <h3 class="modal-title">Simulation Details</h3>

          <div class="modal-field">
            <label>ID</label>
            <code>{{ selectedSim.id }}</code>
          </div>

          <div class="modal-field">
            <label>Status</label>
            <span class="status-badge" :class="statusClass(selectedSim.status)">
              {{ selectedSim.status }}
            </span>
          </div>

          <div class="modal-field">
            <label>Requirement</label>
            <p>{{ selectedSim.requirement || 'N/A' }}</p>
          </div>

          <div class="modal-field" v-if="selectedSim.files && selectedSim.files.length">
            <label>Files</label>
            <div class="modal-files">
              <span v-for="f in selectedSim.files" :key="f" class="file-tag">{{ f }}</span>
            </div>
          </div>

          <div class="modal-field">
            <label>Rounds</label>
            <span>{{ selectedSim.current_round || 0 }} / {{ selectedSim.total_rounds || 0 }}</span>
          </div>

          <div class="modal-field">
            <label>Created</label>
            <span>{{ formatDateFull(selectedSim.created_at) }}</span>
          </div>

          <div class="modal-actions">
            <button
              v-if="selectedSim.project_id"
              class="btn-action"
              @click="navigate('Process', { projectId: selectedSim.project_id })"
            >
              View Graph
            </button>
            <button
              class="btn-action"
              @click="navigate('Simulation', { simulationId: selectedSim.id })"
            >
              View Simulation
            </button>
            <button
              v-if="selectedSim.report_id"
              class="btn-action"
              @click="navigate('Report', { reportId: selectedSim.report_id })"
            >
              View Report
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSimulationHistory } from '@/api/simulation'

export default {
  name: 'HistoryDatabase',
  setup() {
    const router = useRouter()
    const simulations = ref([])
    const loading = ref(false)
    const selectedSim = ref(null)

    const fetchHistory = async () => {
      loading.value = true
      try {
        const res = await getSimulationHistory(20)
        simulations.value = res.data?.simulations || res.data || []
      } catch (e) {
        console.error('[HistoryDatabase] Failed to load history:', e.message)
        simulations.value = []
      } finally {
        loading.value = false
      }
    }

    onMounted(fetchHistory)

    const truncateId = (id) => {
      if (!id) return '---'
      return id.length > 12 ? id.slice(0, 12) + '...' : id
    }

    const truncateText = (text, max) => {
      if (!text) return 'No description'
      return text.length > max ? text.slice(0, max) + '...' : text
    }

    const statusClass = (status) => {
      const s = (status || '').toLowerCase()
      if (s === 'completed') return 'status-completed'
      if (s === 'running') return 'status-running'
      if (s === 'failed') return 'status-failed'
      if (s === 'stopped') return 'status-stopped'
      return 'status-stopped'
    }

    const formatDate = (dt) => {
      if (!dt) return ''
      const d = new Date(dt)
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }

    const formatDateFull = (dt) => {
      if (!dt) return ''
      const d = new Date(dt)
      return d.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
    }

    const openModal = (sim) => { selectedSim.value = sim }
    const closeModal = () => { selectedSim.value = null }

    const navigate = (name, params) => {
      closeModal()
      router.push({ name, params })
    }

    return {
      simulations, loading, selectedSim,
      truncateId, truncateText, statusClass,
      formatDate, formatDateFull,
      openModal, closeModal, navigate,
    }
  },
}
</script>

<style scoped>
.history-database {
  margin-top: 2rem;
}

.history-header {
  margin-bottom: 1.5rem;
}

.history-title {
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: 1.2rem;
  color: #FF4500;
  margin-bottom: 0.5rem;
}

.history-border {
  height: 2px;
  background: linear-gradient(90deg, #FF4500 0%, #FF450033 60%, transparent 100%);
  border-radius: 1px;
}

/* Loading */
.history-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  justify-content: center;
  padding: 2rem;
  color: #888;
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: 0.9rem;
}

/* Empty state */
.history-empty {
  text-align: center;
  padding: 3rem 1rem;
  color: #666;
}

.empty-icon {
  font-size: 2.5rem;
  color: #444;
  margin-bottom: 0.75rem;
}

.empty-hint {
  font-size: 0.8rem;
  color: #555;
  margin-top: 0.5rem;
}

/* Grid */
.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

/* Card */
.history-card {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.15s;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.history-card:hover {
  border-color: #FF4500;
  transform: translateY(-2px);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sim-id {
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: 0.8rem;
  color: #999;
}

/* Status badges */
.status-badge {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  letter-spacing: 0.05em;
}

.status-completed {
  background: #14532d;
  color: #4ade80;
}

.status-running {
  background: #7c2d12;
  color: #fb923c;
  animation: pulse-badge 1.5s ease-in-out infinite;
}

.status-failed {
  background: #7f1d1d;
  color: #f87171;
}

.status-stopped {
  background: #27272a;
  color: #a1a1aa;
}

@keyframes pulse-badge {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.card-requirement {
  font-size: 0.85rem;
  color: #ccc;
  line-height: 1.4;
}

.card-files {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.file-tag {
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: 0.7rem;
  background: #2a2a2a;
  color: #aaa;
  padding: 0.15rem 0.45rem;
  border-radius: 3px;
  border: 1px solid #333;
}

.file-tag-more {
  color: #FF4500;
  border-color: #FF450044;
}

.card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: #777;
  font-family: var(--font-mono, 'Courier New', monospace);
  margin-top: auto;
}

.card-rounds {
  color: #FF4500;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 2rem;
  width: 90%;
  max-width: 520px;
  position: relative;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-close {
  position: absolute;
  top: 0.75rem;
  right: 1rem;
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
}

.modal-close:hover {
  color: #ccc;
}

.modal-title {
  font-family: var(--font-mono, 'Courier New', monospace);
  color: #FF4500;
  font-size: 1.1rem;
  margin-bottom: 1.5rem;
}

.modal-field {
  margin-bottom: 1rem;
}

.modal-field label {
  display: block;
  font-size: 0.75rem;
  color: #777;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}

.modal-field code {
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: 0.85rem;
  color: #ddd;
  word-break: break-all;
}

.modal-field p {
  font-size: 0.9rem;
  color: #ccc;
  line-height: 1.5;
  margin: 0;
}

.modal-files {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #2a2a2a;
}

.btn-action {
  padding: 0.55rem 1.25rem;
  background: transparent;
  color: #FF4500;
  border: 1px solid #FF4500;
  border-radius: 4px;
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.btn-action:hover {
  background: #FF4500;
  color: #0a0a0a;
}

/* Spinner reuse */
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: #FF4500;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 600px) {
  .history-grid {
    grid-template-columns: 1fr;
  }
}
</style>
