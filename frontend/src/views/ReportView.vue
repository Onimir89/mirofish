<template>
  <div class="view-shell">
    <!-- Top bar -->
    <header class="topbar">
      <router-link to="/" class="topbar-brand">
        <span class="brand-name">MiroFish</span>
        <span class="brand-sep">/</span>
        <span class="brand-context">{{ $t('report.context') }}</span>
      </router-link>
      <div class="topbar-actions">
        <div class="topbar-status">
          <span class="status-dot" :class="statusClass"></span>
          <span class="status-text">{{ statusLabel }}</span>
        </div>
        <button
          v-if="isCompleted"
          class="btn-accent-sm"
          @click="goToInteraction"
        >{{ $t('report.go_to_interaction') }} &rarr;</button>
      </div>
    </header>

    <!-- Split layout -->
    <div class="split-layout">
      <!-- Left: Report content -->
      <div class="panel-left report-content">
        <!-- Generation progress -->
        <div v-if="generating" class="gen-overlay">
          <div class="gen-card">
            <div class="spinner-lg"></div>
            <h3>{{ $t('report.generating') }}</h3>
            <p class="hint-text">{{ $t('report.generating_hint') }}</p>
            <div class="log-output">
              <div class="log-line" v-for="(line, i) in genLogs" :key="i">
                <span class="log-prefix">[{{ formatTime(line.time) }}]</span>
                <span class="log-text">{{ line.text }}</span>
              </div>
              <div class="log-cursor"></div>
            </div>
          </div>
        </div>

        <!-- Report document -->
        <div v-if="!generating && report" class="report-doc">
          <h1 class="report-title">{{ report.title || $t('report.default_title') }}</h1>

          <div v-if="report.summary" class="report-summary">
            <div class="summary-content" v-html="renderMarkdown(report.summary)"></div>
          </div>

          <ReportSections
            :sections="sections"
            :expanded-sections="expandedSections"
            @toggle-section="toggleSection"
          />
        </div>
      </div>

      <!-- Right: Generation Timeline -->
      <div class="panel-right timeline-panel">
        <div class="timeline-header">
          <h3>{{ $t('report.generation_timeline') }}</h3>
        </div>

        <div class="timeline-feed">
          <div
            v-for="(event, i) in timelineEvents"
            :key="i"
            class="timeline-item"
          >
            <div class="tl-dot" :class="event.status"></div>
            <div class="tl-body">
              <span class="tl-agent" v-if="event.agent">{{ event.agent }}</span>
              <span class="tl-action">{{ event.action }}</span>
              <span class="tl-time">{{ formatTime(event.timestamp) }}</span>
            </div>
          </div>

          <div v-if="!timelineEvents.length" class="timeline-empty">
            <p>{{ $t('report.no_activity') }}</p>
          </div>
        </div>

        <!-- Graph panel in right sidebar -->
        <div class="sidebar-graph">
          <GraphPanel
            :graph-data="graphData"
            :loading="false"
            current-phase="Report"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '@/components/GraphPanel.vue'
import ReportSections from '@/components/ReportSections.vue'
import { getReport, getReportStatus, getReportSections } from '@/api/report'
import { getSimulation, getSimulationTimeline } from '@/api/simulation'
import { getGraphData } from '@/api/graph'
import { useMarkdown } from '@/composables/useMarkdown'
import { usePolling } from '@/composables/usePolling'
import { useStatus } from '@/composables/useStatus'
import { formatTime } from '@/utils/formatters'

export default {
  name: 'ReportView',
  components: { GraphPanel, ReportSections },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const reportId = route.params.reportId

    const generating = ref(true)
    const report = ref(null)
    const sections = ref([])
    const expandedSections = ref({})
    const graphData = ref({ nodes: [], edges: [] })
    const timelineEvents = ref([])
    const genLogs = ref([])

    const { statusClass, statusLabel, update: updateStatus } = useStatus('active', 'Generating')
    const { renderMarkdown } = useMarkdown()

    const isCompleted = computed(() => !generating.value && report.value)

    const addLog = (text) => {
      genLogs.value.push({ time: new Date(), text })
    }

    const toggleSection = (idx) => {
      expandedSections.value[idx] = !expandedSections.value[idx]
    }

    const goToInteraction = () => {
      router.push(`/interaction/${reportId}`)
    }

    const loadReport = async () => {
      addLog('Checking report status...')

      try {
        const statusRes = await getReportStatus(reportId)
        const status = statusRes.data

        if (status.status === 'completed' || status.status === 'ready') {
          await fetchReport()
        } else if (status.status === 'failed') {
          generating.value = false
          updateStatus('error', 'Failed')
          addLog('Report generation failed: ' + (status.error || ''))
        } else {
          addLog('Report generation in progress...')
          startPolling()
        }
      } catch (e) {
        try {
          await fetchReport()
        } catch (_) {
          addLog('Waiting for report generation...')
          startPolling()
        }
      }
    }

    const fetchReport = async () => {
      const res = await getReport(reportId)
      report.value = res.data
      addLog('Report loaded successfully')

      try {
        const secRes = await getReportSections(reportId)
        sections.value = Array.isArray(secRes.data) ? secRes.data : secRes.data.sections || []
        if (sections.value.length) {
          expandedSections.value[0] = true
        }
      } catch (_) {
        if (report.value.sections) {
          sections.value = report.value.sections
          if (sections.value.length) expandedSections.value[0] = true
        }
      }

      if (report.value.simulation_id) {
        try {
          const sim = await getSimulation(report.value.simulation_id)
          if (sim.data.graph_id) {
            const gRes = await getGraphData(sim.data.graph_id)
            graphData.value = gRes.data
          }
        } catch (_) {}

        try {
          const tlRes = await getSimulationTimeline(report.value.simulation_id)
          timelineEvents.value = Array.isArray(tlRes.data) ? tlRes.data : tlRes.data.events || []
        } catch (_) {}
      }

      generating.value = false
      updateStatus('success', 'Complete')
    }

    const { start: startPolling, stop: stopPolling } = usePolling(async () => {
      try {
        const statusRes = await getReportStatus(reportId)
        const status = statusRes.data

        if (status.status === 'completed' || status.status === 'ready') {
          stopPolling()
          await fetchReport()
        } else if (status.status === 'failed') {
          stopPolling()
          generating.value = false
          updateStatus('error', 'Failed')
        } else {
          addLog(`Status: ${status.status}...`)
        }
      } catch (_) {}
    }, 2000)

    onMounted(() => {
      loadReport()
    })

    return {
      generating,
      report,
      sections,
      expandedSections,
      graphData,
      timelineEvents,
      genLogs,
      statusClass,
      statusLabel,
      isCompleted,
      formatTime,
      renderMarkdown,
      toggleSection,
      goToInteraction,
    }
  },
}
</script>

<style scoped>
.report-content {
  overflow-y: auto;
  padding: 2rem 3rem;
}

.timeline-panel {
  width: 380px;
  display: flex;
  flex-direction: column;
}

/* Generation overlay */
.gen-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.gen-card {
  text-align: center;
  max-width: 500px;
}

.gen-card h3 {
  font-family: var(--font-heading);
  color: var(--text-primary);
  margin: 1rem 0 0.5rem;
}

.gen-card .hint-text {
  margin-bottom: 1.5rem;
}

.gen-card .log-output {
  text-align: left;
}

/* Report document */
.report-doc {
  max-width: 800px;
}

.report-title {
  font-family: var(--font-heading);
  font-size: 2rem;
  color: var(--text-primary);
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.report-summary {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.summary-content {
  font-size: 0.9rem;
  color: #ccc;
  line-height: 1.7;
}

.summary-content :deep(strong) {
  color: var(--text-primary);
}

.summary-content :deep(code) {
  background: #111;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--accent);
}

/* Timeline */
.timeline-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
}

.timeline-header h3 {
  font-family: var(--font-heading);
  font-size: 0.9rem;
  color: var(--text-primary);
  margin: 0;
}

.timeline-feed {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0;
  min-height: 200px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
}

.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border);
  margin-top: 6px;
  flex-shrink: 0;
}

.tl-dot.completed { background: var(--success); }
.tl-dot.running { background: var(--accent); animation: pulse 1.5s infinite; }
.tl-dot.pending { background: var(--border); }

.tl-body {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  font-size: 0.8rem;
}

.tl-agent {
  color: var(--accent);
  font-weight: 600;
}

.tl-action {
  color: #aaa;
}

.tl-time {
  color: #444;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  margin-left: auto;
}

.timeline-empty {
  padding: 2rem;
  text-align: center;
  color: #444;
  font-size: 0.8rem;
}

/* Sidebar graph */
.sidebar-graph {
  height: 250px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .report-content {
    padding: 1rem;
  }
}
</style>
