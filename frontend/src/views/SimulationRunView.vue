<template>
  <div class="view-shell">
    <!-- Top bar -->
    <header class="topbar">
      <router-link to="/" class="topbar-brand">
        <span class="brand-name">MiroFish</span>
        <span class="brand-sep">/</span>
        <span class="brand-context">{{ $t('simulation_run.context') }}</span>
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
      <div class="topbar-actions">
        <div class="topbar-status">
          <span class="status-dot" :class="runStatusClass"></span>
          <span class="status-text">{{ runStatusLabel }}</span>
        </div>
        <button
          v-if="isRunning"
          class="btn-danger-sm"
          @click="handleStop"
        >{{ $t('simulation_run.stop') }}</button>
        <button
          v-if="isCompleted"
          class="btn-accent-sm"
          @click="generateReportAction"
          :disabled="reportLoading"
        >
          <span v-if="reportLoading" class="spinner-xs"></span>
          {{ $t('simulation_run.generate_report') }}
        </button>
      </div>
    </header>

    <!-- Split layout -->
    <div class="split-layout" :class="'mode-' + viewMode">
      <!-- Left: Graph -->
      <div class="panel-left" v-show="isGraphVisible()">
        <GraphPanel
          :graph-data="graphData"
          :loading="graphLoading"
          current-phase="Running"
        />
      </div>

      <!-- Right: Feed -->
      <div class="panel-right run-panel" v-show="isWorkbenchVisible()">
        <!-- Platform Status Cards -->
        <div class="platform-status-row">
          <div class="platform-card" v-for="p in platforms" :key="p.name">
            <div class="platform-header">
              <span class="platform-icon" v-html="platformIcon(p.name)"></span>
              <span class="platform-name">{{ p.name }}</span>
            </div>
            <div class="platform-stats">
              <div class="pstat">
                <span class="pstat-value">{{ p.round || 0 }}</span>
                <span class="pstat-label">{{ $t('simulation_run.round') }}</span>
              </div>
              <div class="pstat">
                <span class="pstat-value">{{ p.actions || 0 }}</span>
                <span class="pstat-label">{{ $t('simulation_run.actions') }}</span>
              </div>
            </div>
            <div class="platform-progress">
              <div class="ppbar">
                <div class="ppfill" :style="{ width: p.progress + '%' }"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Timeline Feed -->
        <div class="feed-header">
          <h3>{{ $t('simulation_run.activity_feed') }}</h3>
          <span class="feed-count">{{ timeline.length }} {{ $t('simulation_run.actions_count') }}</span>
        </div>

        <div class="feed-list" ref="feedRef">
          <div
            v-for="(action, i) in timeline"
            :key="i"
            class="feed-item"
          >
            <div class="feed-icon" :class="actionClass(action.type)" v-html="actionIcon(action.type)"></div>
            <div class="feed-body">
              <div class="feed-meta">
                <span class="feed-agent" :style="{ color: agentColor(action.agent) }">{{ action.agent }}</span>
                <span class="feed-type">{{ formatActionType(action.type) }}</span>
                <span class="feed-time">{{ formatTime(action.timestamp) }}</span>
              </div>
              <div v-if="action.content" class="feed-content">
                {{ truncate(action.content, 280) }}
              </div>
              <div v-if="action.target" class="feed-target">
                <span class="target-label">re:</span> {{ action.target }}
              </div>
            </div>
          </div>

          <div v-if="!timeline.length && isRunning" class="feed-empty">
            <div class="spinner-md"></div>
            <p>{{ $t('simulation_run.waiting_actions') }}</p>
          </div>

          <div v-if="!timeline.length && !isRunning && !isCompleted" class="feed-empty">
            <p>{{ $t('simulation_run.starting_simulation') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import GraphPanel from '@/components/GraphPanel.vue'
import {
  startSimulation,
  stopSimulation,
  getRunStatus,
  getRunStatusDetail,
  getSimulationActions,
  getSimulation,
} from '@/api/simulation'
import { generateReport } from '@/api/report'
import { getGraphData } from '@/api/graph'
import { usePolling } from '@/composables/usePolling'
import { useViewMode } from '@/composables/useViewMode'
import { formatTime } from '@/utils/formatters'
import { getAgentColor } from '@/utils/agentColors'

export default {
  name: 'SimulationRunView',
  components: { GraphPanel },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { t } = useI18n()
    const simulationId = route.params.simulationId
    const { viewMode, setMode, isGraphVisible, isWorkbenchVisible } = useViewMode('split')

    const graphData = ref({ nodes: [], edges: [] })
    const graphLoading = ref(false)
    const runStatus = ref('starting')
    const platforms = ref([
      { name: 'Twitter', round: 0, actions: 0, progress: 0 },
      { name: 'Reddit', round: 0, actions: 0, progress: 0 },
    ])
    const timeline = ref([])
    const reportLoading = ref(false)
    const feedRef = ref(null)

    const isRunning = computed(() => runStatus.value === 'running')
    const isCompleted = computed(() => runStatus.value === 'completed')

    const runStatusClass = computed(() => {
      if (isRunning.value) return 'active'
      if (isCompleted.value) return 'success'
      if (runStatus.value === 'failed') return 'error'
      return 'pending'
    })

    const runStatusLabel = computed(() => {
      const key = `simulation_run.status_${runStatus.value}`
      const translated = t(key)
      return translated !== key ? translated : runStatus.value
    })

    const agentColor = getAgentColor

    const formatActionType = (type) => {
      const map = {
        CREATE_POST: 'posted',
        LIKE_POST: 'liked',
        REPOST: 'reposted',
        QUOTE_POST: 'quoted',
        CREATE_COMMENT: 'commented',
        FOLLOW: 'followed',
        DO_NOTHING: 'idle',
      }
      return map[type] || type
    }

    const truncate = (text, max) => {
      if (!text) return ''
      return text.length > max ? text.slice(0, max) + '...' : text
    }

    const actionIcon = (type) => {
      const icons = {
        CREATE_POST: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        LIKE_POST: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>',
        REPOST: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 014-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 01-4 4H3"/></svg>',
        QUOTE_POST: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/><line x1="9" y1="9" x2="15" y2="9"/></svg>',
        CREATE_COMMENT: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></svg>',
        FOLLOW: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>',
        DO_NOTHING: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
      }
      return icons[type] || icons.DO_NOTHING
    }

    const actionClass = (type) => {
      const map = {
        CREATE_POST: 'action-post',
        LIKE_POST: 'action-like',
        REPOST: 'action-repost',
        QUOTE_POST: 'action-quote',
        CREATE_COMMENT: 'action-comment',
        FOLLOW: 'action-follow',
        DO_NOTHING: 'action-idle',
      }
      return map[type] || 'action-idle'
    }

    const platformIcon = (name) => {
      if (name === 'Twitter') {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
      }
      return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12c0 4.42 2.87 8.17 6.84 9.49.5.09.68-.22.68-.48 0-.24-.01-.87-.01-1.71-2.78.6-3.37-1.34-3.37-1.34-.45-1.15-1.11-1.46-1.11-1.46-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.89 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.56 9.56 0 0112 6.8c.85 0 1.71.11 2.51.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85 0 1.34-.01 2.42-.01 2.75 0 .27.18.58.69.48A10.01 10.01 0 0022 12c0-5.52-4.48-10-10-10z"/></svg>'
    }

    const autoStart = async () => {
      try {
        const sim = await getSimulation(simulationId)
        if (sim.data.graph_id) {
          graphLoading.value = true
          try {
            const gRes = await getGraphData(sim.data.graph_id)
            graphData.value = gRes.data
          } catch (_) {}
          graphLoading.value = false
        }

        runStatus.value = 'starting'
        await startSimulation(simulationId, {})
        runStatus.value = 'running'
        startPolling()
      } catch (e) {
        runStatus.value = 'running'
        startPolling()
      }
    }

    const pollStatusFn = async () => {
      try {
        const res = await getRunStatusDetail(simulationId)
        const data = res.data

        runStatus.value = data.status || 'running'

        if (data.platforms) {
          platforms.value = Object.entries(data.platforms).map(([name, info]) => ({
            name,
            round: info.current_round || 0,
            actions: info.action_count || 0,
            progress: info.total_rounds ? Math.round((info.current_round / info.total_rounds) * 100) : 0,
          }))
        } else if (data.current_round != null) {
          platforms.value = platforms.value.map((p) => ({
            ...p,
            round: data.current_round || 0,
            progress: data.total_rounds ? Math.round((data.current_round / data.total_rounds) * 100) : 0,
          }))
        }

        if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
          statusPoller.stop()
          actionsPoller.stop()
        }
      } catch (_) {
        try {
          const res = await getRunStatus(simulationId)
          runStatus.value = res.data.status || 'running'
        } catch (__) {}
      }
    }

    const pollActionsFn = async () => {
      try {
        const res = await getSimulationActions(simulationId, { limit: 100 })
        const actions = Array.isArray(res.data) ? res.data : res.data.actions || []
        if (actions.length > timeline.value.length) {
          timeline.value = actions
          await nextTick()
          scrollFeed()
        }
      } catch (_) {}
    }

    const statusPoller = usePolling(pollStatusFn, 2000)
    const actionsPoller = usePolling(pollActionsFn, 2000)

    const startPolling = () => {
      statusPoller.start()
      actionsPoller.start()
    }

    const scrollFeed = () => {
      if (feedRef.value) {
        feedRef.value.scrollTop = feedRef.value.scrollHeight
      }
    }

    const handleStop = async () => {
      try {
        await stopSimulation(simulationId)
        runStatus.value = 'stopped'
      } catch (e) {
        // Already stopped
      }
    }

    const generateReportAction = async () => {
      reportLoading.value = true
      try {
        const res = await generateReport(simulationId)
        const reportId = res.data.report_id || res.data.id
        reportLoading.value = false
        router.push(`/report/${reportId}`)
      } catch (e) {
        reportLoading.value = false
      }
    }

    onMounted(() => {
      autoStart()
    })

    return {
      viewMode,
      setMode,
      isGraphVisible,
      isWorkbenchVisible,
      graphData,
      graphLoading,
      runStatus,
      runStatusClass,
      runStatusLabel,
      isRunning,
      isCompleted,
      platforms,
      timeline,
      reportLoading,
      feedRef,
      agentColor,
      formatTime,
      formatActionType,
      truncate,
      actionIcon,
      actionClass,
      platformIcon,
      handleStop,
      generateReportAction,
    }
  },
}
</script>

<style scoped>
.run-panel {
  width: 460px;
  display: flex;
  flex-direction: column;
}

/* Platform status */
.platform-status-row {
  display: flex;
  gap: 0.75rem;
  padding: 1rem;
  border-bottom: 1px solid var(--border);
}

.platform-card {
  flex: 1;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.platform-icon {
  color: var(--text-secondary);
  display: flex;
  align-items: center;
}

.platform-name {
  font-size: 0.8rem;
  color: #ccc;
  font-weight: 600;
}

.platform-stats {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.pstat {
  text-align: center;
}

.pstat-value {
  display: block;
  font-family: var(--font-heading);
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
}

.pstat-label {
  display: block;
  font-size: 0.6rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ppbar {
  height: 3px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}

.ppfill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
  border-radius: 2px;
}

/* Feed */
.feed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
}

.feed-header h3 {
  font-family: var(--font-heading);
  font-size: 0.9rem;
  color: var(--text-primary);
  margin: 0;
}

.feed-count {
  font-size: 0.75rem;
  color: #555;
  font-family: var(--font-mono);
}

.feed-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0;
}

.feed-item {
  display: flex;
  gap: 0.75rem;
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--bg-secondary);
  transition: background 0.15s;
}

.feed-item:hover {
  background: #111;
}

.feed-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.feed-icon.action-post { background: rgba(65, 105, 225, 0.15); color: #4169E1; }
.feed-icon.action-like { background: rgba(220, 20, 60, 0.15); color: var(--danger); }
.feed-icon.action-repost { background: rgba(46, 139, 87, 0.15); color: var(--success); }
.feed-icon.action-quote { background: rgba(123, 45, 142, 0.15); color: #7B2D8E; }
.feed-icon.action-comment { background: rgba(255, 140, 0, 0.15); color: #FF8C00; }
.feed-icon.action-follow { background: rgba(0, 78, 137, 0.15); color: #004E89; }
.feed-icon.action-idle { background: rgba(136, 136, 136, 0.1); color: #555; }

.feed-body {
  flex: 1;
  min-width: 0;
}

.feed-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  flex-wrap: wrap;
}

.feed-agent {
  font-size: 0.8rem;
  font-weight: 600;
}

.feed-type {
  font-size: 0.75rem;
  color: #666;
}

.feed-time {
  font-size: 0.7rem;
  color: #444;
  font-family: var(--font-mono);
  margin-left: auto;
}

.feed-content {
  font-size: 0.8rem;
  color: #bbb;
  line-height: 1.5;
  margin-top: 0.2rem;
}

.feed-target {
  font-size: 0.75rem;
  color: #666;
  margin-top: 0.2rem;
}

.target-label {
  color: #444;
  font-style: italic;
}

.feed-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  gap: 1rem;
  color: #555;
  font-size: 0.85rem;
}

@media (max-width: 768px) {
  .platform-status-row {
    flex-direction: column;
  }
}
</style>
