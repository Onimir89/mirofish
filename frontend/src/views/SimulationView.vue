<template>
  <div class="view-shell">
    <!-- Top bar -->
    <header class="topbar">
      <router-link to="/" class="topbar-brand">
        <span class="brand-name">MiroFish</span>
        <span class="brand-sep">/</span>
        <span class="brand-context">{{ $t('simulation.context') }}</span>
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
          current-phase="Environment Setup"
        />
      </div>

      <!-- Right: Env Setup -->
      <div class="panel-right sim-panel" v-show="isWorkbenchVisible()">
        <!-- Loading state -->
        <div v-if="preparing" class="step-card">
          <div class="step-header">
            <div class="step-number active-spin">
              <span class="spinner-sm"></span>
            </div>
            <h2>{{ $t('simulation.preparing') }}</h2>
          </div>
          <div class="step-body">
            <p class="hint-text">{{ $t('simulation.preparing_hint') }}</p>
            <div class="log-output">
              <div class="log-line" v-for="(line, i) in prepLogs" :key="i">
                <span class="log-prefix">[{{ formatTime(line.time) }}]</span>
                <span class="log-text">{{ line.text }}</span>
              </div>
              <div class="log-cursor"></div>
            </div>
          </div>
        </div>

        <!-- Agent Profiles -->
        <div v-if="!preparing && profiles.length" class="step-card">
          <div class="step-header">
            <div class="step-number active">&#9679;</div>
            <h2>{{ $t('simulation.agent_profiles') }} <span class="count">({{ profiles.length }})</span></h2>
          </div>
          <div class="step-body">
            <div class="profile-list">
              <div
                v-for="agent in profiles"
                :key="agent.id || agent.name"
                class="profile-card"
                :class="{ expanded: expandedAgent === agent.name }"
                @click="toggleAgent(agent.name)"
              >
                <div class="profile-header">
                  <div class="profile-avatar" :style="{ background: agentColor(agent.name) }">
                    {{ agentInitial(agent.name) }}
                  </div>
                  <div class="profile-info">
                    <span class="profile-name">{{ agent.name }}</span>
                    <span class="profile-role">{{ agent.role || 'Agent' }}</span>
                  </div>
                  <span class="expand-icon">{{ expandedAgent === agent.name ? '&#9660;' : '&#9654;' }}</span>
                </div>
                <transition name="expand">
                  <div v-if="expandedAgent === agent.name" class="profile-details">
                    <div v-if="agent.bio" class="profile-field">
                      <span class="field-label">{{ $t('simulation.bio') }}</span>
                      <p class="field-value">{{ agent.bio }}</p>
                    </div>
                    <div v-if="agent.topics && agent.topics.length" class="profile-field">
                      <span class="field-label">{{ $t('simulation.topics') }}</span>
                      <div class="topic-tags">
                        <span v-for="t in agent.topics" :key="t" class="topic-tag">{{ t }}</span>
                      </div>
                    </div>
                    <div v-if="agent.stance" class="profile-field">
                      <span class="field-label">{{ $t('simulation.stance') }}</span>
                      <p class="field-value">{{ agent.stance }}</p>
                    </div>
                    <div v-if="agent.personality" class="profile-field">
                      <span class="field-label">{{ $t('simulation.personality') }}</span>
                      <p class="field-value">{{ agent.personality }}</p>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
          </div>
        </div>

        <!-- Simulation Config -->
        <div v-if="!preparing && simConfig" class="step-card">
          <div class="step-header">
            <div class="step-number">&#9881;</div>
            <h2>{{ $t('simulation.sim_config') }}</h2>
          </div>
          <div class="step-body">
            <div class="config-grid">
              <div v-if="simConfig.duration" class="config-item">
                <span class="config-label">{{ $t('simulation.duration') }}</span>
                <span class="config-value">{{ simConfig.duration }}</span>
              </div>
              <div v-if="simConfig.platforms" class="config-item">
                <span class="config-label">{{ $t('simulation.platforms') }}</span>
                <span class="config-value">{{ Array.isArray(simConfig.platforms) ? simConfig.platforms.join(', ') : simConfig.platforms }}</span>
              </div>
              <div v-if="simConfig.events_count != null" class="config-item">
                <span class="config-label">{{ $t('simulation.events') }}</span>
                <span class="config-value">{{ simConfig.events_count }}</span>
              </div>
            </div>

            <!-- Custom rounds -->
            <div class="rounds-input">
              <label class="config-label">{{ $t('simulation.rounds') }}</label>
              <div class="input-row">
                <input
                  v-model.number="customRounds"
                  type="number"
                  min="1"
                  max="100"
                  class="number-input"
                />
                <span class="input-hint">{{ $t('simulation.rounds_hint') }}</span>
              </div>
            </div>

            <button class="btn-accent" @click="startSim" :disabled="startLoading">
              <span v-if="startLoading" class="spinner"></span>
              {{ startLoading ? $t('simulation.starting') : $t('simulation.start_simulation') }}
            </button>
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="error-card">
          <p>{{ error }}</p>
          <button class="btn-ghost" @click="error = ''">{{ $t('simulation.dismiss') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '@/components/GraphPanel.vue'
import {
  getSimulation,
  prepareSimulation,
  getPrepareStatus,
  getSimulationProfiles,
  getSimulationConfig,
} from '@/api/simulation'
import { getGraphData } from '@/api/graph'
import { formatTime } from '@/utils/formatters'
import { getAgentColor } from '@/utils/agentColors'
import { useStatus } from '@/composables/useStatus'
import { usePolling } from '@/composables/usePolling'
import { useViewMode } from '@/composables/useViewMode'

export default {
  name: 'SimulationView',
  components: { GraphPanel },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const simulationId = route.params.simulationId
    const { viewMode, setMode, isGraphVisible, isWorkbenchVisible } = useViewMode('split')

    const preparing = ref(true)
    const error = ref('')
    const graphData = ref({ nodes: [], edges: [] })
    const graphLoading = ref(false)
    const profiles = ref([])
    const simConfig = ref(null)
    const customRounds = ref(5)
    const expandedAgent = ref(null)
    const startLoading = ref(false)
    const { statusClass, statusLabel, update: updateStatus } = useStatus('active', 'Preparing')
    const prepLogs = ref([])

    const addLog = (text) => {
      prepLogs.value.push({ time: new Date(), text })
    }

    const agentColor = getAgentColor

    const agentInitial = (name) => (name || '?')[0].toUpperCase()

    const toggleAgent = (name) => {
      expandedAgent.value = expandedAgent.value === name ? null : name
    }

    const prepPoller = usePolling(async () => {
      try {
        const res = await getPrepareStatus(simulationId)
        const status = res.data

        if (status.status === 'completed' || status.status === 'prepared' || status.status === 'ready') {
          prepPoller.stop()
          addLog('Preparation complete!')
          await loadProfilesAndConfig()
          preparing.value = false
          updateStatus('success', 'Ready')
        } else if (status.status === 'failed') {
          prepPoller.stop()
          error.value = status.error || 'Preparation failed'
          preparing.value = false
          updateStatus('error', 'Failed')
        } else {
          addLog(`Status: ${status.status}...`)
        }
      } catch (_) { /* continue polling */ }
    }, 2000)

    const loadSimulation = async () => {
      try {
        addLog('Loading simulation data...')
        const res = await getSimulation(simulationId)
        const sim = res.data

        if (sim.graph_id) {
          graphLoading.value = true
          try {
            const gRes = await getGraphData(sim.graph_id)
            graphData.value = gRes.data
          } catch (_) { /* no graph yet */ }
          graphLoading.value = false
        }

        if (sim.status === 'prepared' || sim.status === 'ready') {
          await loadProfilesAndConfig()
          preparing.value = false
          updateStatus('success', 'Ready')
        } else {
          addLog('Preparing simulation environment...')
          await prepareSimulation(simulationId)
          prepPoller.start()
        }
      } catch (e) {
        error.value = e.response?.data?.error || e.message
        preparing.value = false
        updateStatus('error', 'Error')
      }
    }

    const loadProfilesAndConfig = async () => {
      try {
        const [profRes, confRes] = await Promise.all([
          getSimulationProfiles(simulationId).catch(() => ({ data: [] })),
          getSimulationConfig(simulationId).catch(() => ({ data: {} })),
        ])
        profiles.value = Array.isArray(profRes.data) ? profRes.data : profRes.data.profiles || []
        simConfig.value = confRes.data || {}
        if (simConfig.value.rounds) {
          customRounds.value = simConfig.value.rounds
        }
      } catch (_) { /* use defaults */ }
    }

    const startSim = async () => {
      startLoading.value = true
      try {
        router.push(`/simulation/${simulationId}/start`)
      } catch (e) {
        error.value = e.message
        startLoading.value = false
      }
    }

    onMounted(() => {
      loadSimulation()
    })

    return {
      viewMode,
      setMode,
      isGraphVisible,
      isWorkbenchVisible,
      preparing,
      error,
      graphData,
      graphLoading,
      profiles,
      simConfig,
      customRounds,
      expandedAgent,
      startLoading,
      statusClass,
      statusLabel,
      prepLogs,
      formatTime,
      agentColor,
      agentInitial,
      toggleAgent,
      startSim,
    }
  },
}
</script>

<style scoped>
.sim-panel {
  width: 440px;
  padding: 1rem;
  overflow-y: auto;
}

.step-number.active-spin {
  background: transparent;
}

/* Profile cards */
.profile-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.profile-card {
  background: #111;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.profile-card:hover {
  border-color: #3a3a3a;
}

.profile-card.expanded {
  border-color: var(--accent);
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
}

.profile-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-family: var(--font-heading);
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.profile-info {
  flex: 1;
  min-width: 0;
}

.profile-name {
  display: block;
  font-size: 0.85rem;
  color: var(--text-primary);
  font-weight: 600;
}

.profile-role {
  display: block;
  font-size: 0.7rem;
  color: #666;
}

.expand-icon {
  color: #555;
  font-size: 0.7rem;
}

.profile-details {
  padding: 0 1rem 1rem;
  border-top: 1px solid var(--border);
}

.profile-field {
  margin-top: 0.75rem;
}

.field-label {
  display: block;
  font-size: 0.7rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.2rem;
  font-family: var(--font-mono);
}

.field-value {
  font-size: 0.8rem;
  color: #bbb;
  line-height: 1.5;
  margin: 0;
}

.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.topic-tag {
  padding: 0.15rem 0.5rem;
  background: rgba(255, 69, 0, 0.1);
  border: 1px solid rgba(255, 69, 0, 0.2);
  border-radius: 4px;
  font-size: 0.7rem;
  color: var(--accent);
  font-family: var(--font-mono);
}

/* Config */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.config-item {
  background: #111;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
}

.config-label {
  display: block;
  font-size: 0.7rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
  font-family: var(--font-mono);
}

.config-value {
  font-size: 0.85rem;
  color: var(--text-primary);
}

.rounds-input {
  margin-bottom: 1.25rem;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.35rem;
}

.number-input {
  width: 80px;
  padding: 0.5rem 0.75rem;
  background: #111;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.9rem;
  text-align: center;
}

.number-input:focus {
  outline: none;
  border-color: var(--accent);
}

.input-hint {
  font-size: 0.75rem;
  color: #555;
}

/* Transitions */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  max-height: 300px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
