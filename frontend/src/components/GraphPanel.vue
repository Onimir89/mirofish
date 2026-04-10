<template>
  <div class="graph-panel" ref="panelRef">
    <!-- Loading overlay -->
    <div v-if="loading" class="graph-loading">
      <div class="loading-spinner"></div>
      <p>Building graph...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!hasData" class="graph-empty">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="1.5">
          <circle cx="5" cy="6" r="2"/>
          <circle cx="19" cy="6" r="2"/>
          <circle cx="12" cy="18" r="2"/>
          <line x1="7" y1="6" x2="17" y2="6"/>
          <line x1="6" y1="8" x2="11" y2="16"/>
          <line x1="18" y1="8" x2="13" y2="16"/>
        </svg>
      </div>
      <p>No graph data yet</p>
    </div>

    <!-- SVG container -->
    <svg v-show="hasData && !loading" ref="svgRef" class="graph-svg"></svg>

    <!-- Fullscreen toggle -->
    <button v-if="hasData" class="fullscreen-btn" @click="$emit('toggle-maximize')" title="Toggle fullscreen">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="15 3 21 3 21 9"/>
        <polyline points="9 21 3 21 3 15"/>
        <line x1="21" y1="3" x2="14" y2="10"/>
        <line x1="3" y1="21" x2="10" y2="14"/>
      </svg>
    </button>

    <!-- Node/Edge detail panel -->
    <transition name="slide">
      <div v-if="selectedItem" class="detail-panel">
        <div class="detail-header">
          <h4>{{ selectedItem.type === 'node' ? 'Entity' : 'Relation' }}</h4>
          <button class="detail-close" @click="clearSelection">&times;</button>
        </div>
        <div class="detail-body">
          <template v-if="selectedItem.type === 'node'">
            <div class="detail-row">
              <span class="detail-label">Name</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Type</span>
              <span class="detail-value">
                <span class="type-badge" :style="{ background: getNodeColor(selectedItem.data.type) }">
                  {{ selectedItem.data.type }}
                </span>
              </span>
            </div>
            <div v-if="selectedItem.data.id" class="detail-row">
              <span class="detail-label">UUID</span>
              <span class="detail-value uuid">{{ selectedItem.data.id }}</span>
            </div>
            <div v-if="selectedItem.data.created_at" class="detail-row">
              <span class="detail-label">Created</span>
              <span class="detail-value">{{ selectedItem.data.created_at }}</span>
            </div>
            <div v-if="selectedItem.data.description" class="detail-row">
              <span class="detail-label">Description</span>
              <span class="detail-value desc">{{ selectedItem.data.description }}</span>
            </div>
            <div v-if="selectedItem.data.summary" class="detail-row">
              <span class="detail-label">Summary</span>
              <span class="detail-value desc">{{ selectedItem.data.summary }}</span>
            </div>
            <template v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length">
              <div class="detail-row">
                <span class="detail-label">Attributes</span>
              </div>
              <div
                v-for="(val, key) in selectedItem.data.attributes"
                :key="key"
                class="detail-row attr-row"
              >
                <span class="detail-attr-key">{{ key }}</span>
                <span class="detail-attr-val">{{ val }}</span>
              </div>
            </template>
          </template>
          <template v-else>
            <div class="detail-row">
              <span class="detail-label">Connection</span>
              <span class="detail-value edge-connection">
                {{ selectedItem.data.source?.name || selectedItem.data.source }}
                <span class="edge-arrow">&rarr;</span>
                <span class="edge-relation">{{ selectedItem.data.relation || selectedItem.data.label }}</span>
                <span class="edge-arrow">&rarr;</span>
                {{ selectedItem.data.target?.name || selectedItem.data.target }}
              </span>
            </div>
            <div v-if="selectedItem.data.fact || selectedItem.data.description" class="detail-row">
              <span class="detail-label">Fact</span>
              <span class="detail-value desc">{{ selectedItem.data.fact || selectedItem.data.description }}</span>
            </div>
            <div v-if="selectedItem.data.created_at" class="detail-row">
              <span class="detail-label">Created</span>
              <span class="detail-value">{{ selectedItem.data.created_at }}</span>
            </div>
          </template>
        </div>
      </div>
    </transition>

    <!-- Legend -->
    <div v-if="hasData && legendTypes.length" class="graph-legend">
      <div
        v-for="t in legendTypes"
        :key="t.name"
        class="legend-item"
      >
        <span class="legend-dot" :style="{ background: t.color }"></span>
        <span class="legend-label">{{ t.name }}</span>
      </div>
    </div>

    <!-- Phase indicator -->
    <div v-if="currentPhase" class="phase-badge">
      {{ currentPhase }}
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'

const NODE_COLORS = [
  '#FF6B35', '#004E89', '#7B2D8E', '#2E8B57', '#DC143C',
  '#FF8C00', '#4169E1', '#8B4513', '#008B8B', '#9932CC',
]

export default {
  name: 'GraphPanel',
  props: {
    graphData: {
      type: Object,
      default: () => ({ nodes: [], edges: [] }),
    },
    loading: {
      type: Boolean,
      default: false,
    },
    currentPhase: {
      type: String,
      default: '',
    },
  },
  emits: ['node-click', 'edge-click', 'toggle-maximize'],
  setup(props, { emit }) {
    const panelRef = ref(null)
    const svgRef = ref(null)
    const selectedItem = ref(null)
    let simulation = null
    let svgSelection = null
    let zoomBehavior = null
    let resizeObserver = null
    let resizeTimer = null

    const typeColorMap = ref({})

    const hasData = computed(() => {
      const d = props.graphData
      return d && d.nodes && d.nodes.length > 0
    })

    const legendTypes = computed(() => {
      return Object.entries(typeColorMap.value).map(([name, color]) => ({ name, color }))
    })

    const getNodeColor = (type) => {
      return typeColorMap.value[type] || '#888'
    }

    const buildColorMap = (nodes) => {
      const types = [...new Set(nodes.map((n) => n.type).filter(Boolean))]
      const map = {}
      types.forEach((t, i) => {
        map[t] = NODE_COLORS[i % NODE_COLORS.length]
      })
      typeColorMap.value = map
    }

    // Track D3 selections for highlight updates
    let linkSelection = null
    let nodeGroupSelection = null

    const clearSelection = () => {
      selectedItem.value = null
      applySelectionHighlights()
    }

    const applySelectionHighlights = () => {
      if (!linkSelection || !nodeGroupSelection) return
      const sel = selectedItem.value

      // Edge highlights
      linkSelection
        .attr('stroke', (d) =>
          sel && sel.type === 'edge' && d === sel.data ? '#3498db' : '#3a3a3a'
        )
        .attr('stroke-width', (d) =>
          sel && sel.type === 'edge' && d === sel.data ? 3 : 1.5
        )
        .attr('stroke-opacity', (d) =>
          sel && sel.type === 'edge' && d === sel.data ? 1 : 0.7
        )

      // Node highlights
      nodeGroupSelection.select('circle')
        .attr('r', (d) =>
          sel && sel.type === 'node' && d === sel.data ? 14 : 10
        )
        .attr('stroke', (d) =>
          sel && sel.type === 'node' && d === sel.data ? '#ffffff' : '#1a1a1a'
        )
        .attr('stroke-width', (d) =>
          sel && sel.type === 'node' && d === sel.data ? 3 : 2
        )
    }

    const renderGraph = () => {
      if (!svgRef.value || !hasData.value) return

      const container = panelRef.value
      if (!container) return

      const width = container.clientWidth || 600
      const height = container.clientHeight || 500

      // Clear previous
      if (simulation) {
        simulation.stop()
        simulation = null
      }
      const svg = d3.select(svgRef.value)
      svg.selectAll('*').remove()
      svg.attr('width', width).attr('height', height)

      // Deep-copy to avoid mutating props
      const nodes = props.graphData.nodes.map((n) => ({ ...n }))
      const edges = props.graphData.edges.map((e) => ({
        ...e,
        source: e.source?.id ?? e.source,
        target: e.target?.id ?? e.target,
      }))

      buildColorMap(nodes)
      const colorFn = (type) => typeColorMap.value[type] || '#888'

      // Zoom
      const g = svg.append('g')
      zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
          g.attr('transform', event.transform)
        })
      svg.call(zoomBehavior)

      // Simulation
      simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges).id((d) => d.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-400))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide(50))

      // Edges
      linkSelection = g.append('g')
        .attr('class', 'links')
        .selectAll('line')
        .data(edges)
        .join('line')
        .attr('stroke', '#3a3a3a')
        .attr('stroke-width', 1.5)
        .attr('stroke-opacity', 0.7)
        .style('cursor', 'pointer')
        .on('click', (event, d) => {
          event.stopPropagation()
          selectedItem.value = { type: 'edge', data: d }
          applySelectionHighlights()
          emit('edge-click', d)
        })

      // Edge labels
      const linkLabel = g.append('g')
        .attr('class', 'link-labels')
        .selectAll('text')
        .data(edges)
        .join('text')
        .attr('font-size', 9)
        .attr('fill', '#666')
        .attr('text-anchor', 'middle')
        .attr('font-family', "'JetBrains Mono', monospace")
        .text((d) => d.relation || d.label || '')

      // Node groups
      nodeGroupSelection = g.append('g')
        .attr('class', 'nodes')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .style('cursor', 'pointer')
        .on('click', (event, d) => {
          event.stopPropagation()
          selectedItem.value = { type: 'node', data: d }
          applySelectionHighlights()
          emit('node-click', d)
        })
        .call(dragBehavior(simulation))

      // Node circles
      nodeGroupSelection.append('circle')
        .attr('r', 10)
        .attr('fill', (d) => colorFn(d.type))
        .attr('stroke', '#1a1a1a')
        .attr('stroke-width', 2)

      // Node labels
      nodeGroupSelection.append('text')
        .attr('dx', 14)
        .attr('dy', 4)
        .attr('font-size', 11)
        .attr('fill', '#ccc')
        .attr('font-family', "'Inter', sans-serif")
        .text((d) => d.name || d.id)

      // Click on background to deselect
      svg.on('click', () => {
        clearSelection()
      })

      // Tick
      simulation.on('tick', () => {
        linkSelection
          .attr('x1', (d) => d.source.x)
          .attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x)
          .attr('y2', (d) => d.target.y)

        linkLabel
          .attr('x', (d) => (d.source.x + d.target.x) / 2)
          .attr('y', (d) => (d.source.y + d.target.y) / 2)

        nodeGroupSelection.attr('transform', (d) => `translate(${d.x},${d.y})`)
      })
    }

    const dragBehavior = (sim) => {
      return d3.drag()
        .on('start', (event) => {
          if (!event.active) sim.alphaTarget(0.3).restart()
          event.subject.fx = event.subject.x
          event.subject.fy = event.subject.y
        })
        .on('drag', (event) => {
          event.subject.fx = event.x
          event.subject.fy = event.y
        })
        .on('end', (event) => {
          if (!event.active) sim.alphaTarget(0)
          event.subject.fx = null
          event.subject.fy = null
        })
    }

    watch(
      () => props.graphData,
      () => {
        nextTick(() => renderGraph())
      },
      { deep: true }
    )

    const handleKeydown = (e) => {
      if (e.key === 'Escape') {
        clearSelection()
      }
    }

    onMounted(() => {
      nextTick(() => renderGraph())

      if (panelRef.value && typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          clearTimeout(resizeTimer)
          resizeTimer = setTimeout(() => renderGraph(), 150)
        })
        resizeObserver.observe(panelRef.value)
      }

      window.addEventListener('keydown', handleKeydown)
    })

    onBeforeUnmount(() => {
      if (simulation) simulation.stop()
      if (resizeTimer) clearTimeout(resizeTimer)
      if (resizeObserver) resizeObserver.disconnect()
      window.removeEventListener('keydown', handleKeydown)
    })

    return {
      panelRef,
      svgRef,
      selectedItem,
      hasData,
      legendTypes,
      getNodeColor,
      clearSelection,
    }
  },
}
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #0d0d0d;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  overflow: hidden;
}

.graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #2a2a2a;
  border-top-color: #FF4500;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.graph-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: #555;
  font-size: 0.85rem;
}

.empty-icon {
  opacity: 0.5;
}

/* Fullscreen toggle */
.fullscreen-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 32px;
  height: 32px;
  background: rgba(26, 26, 26, 0.9);
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #888;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 8;
  transition: color 0.15s, border-color 0.15s;
}

.fullscreen-btn:hover {
  color: #e0e0e0;
  border-color: #444;
}

/* Detail panel */
.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 300px;
  height: 100%;
  background: #1a1a1a;
  border-left: 1px solid #2a2a2a;
  overflow-y: auto;
  z-index: 10;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.5);
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #2a2a2a;
}

.detail-header h4 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.85rem;
  color: #e0e0e0;
  margin: 0;
}

.detail-close {
  background: none;
  border: none;
  color: #888;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 0.25rem;
}

.detail-close:hover {
  color: #e0e0e0;
}

.detail-body {
  padding: 0.75rem 1rem;
}

.detail-row {
  margin-bottom: 0.6rem;
}

.detail-label {
  display: block;
  font-size: 0.7rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.15rem;
  font-family: 'JetBrains Mono', monospace;
}

.detail-value {
  font-size: 0.85rem;
  color: #e0e0e0;
}

.detail-value.desc {
  font-size: 0.8rem;
  color: #aaa;
  line-height: 1.4;
}

.type-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #fff;
  font-family: 'JetBrains Mono', monospace;
}

.detail-value.uuid {
  font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace;
  color: #888;
  word-break: break-all;
}

.attr-row {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding-left: 0.5rem;
}

.detail-attr-key {
  font-size: 0.75rem;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
  min-width: 60px;
  flex-shrink: 0;
}

.detail-attr-key::after {
  content: ':';
}

.detail-attr-val {
  font-size: 0.8rem;
  color: #ccc;
  word-break: break-word;
}

.edge-connection {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  line-height: 1.6;
}

.edge-arrow {
  color: #555;
  font-size: 0.75rem;
}

.edge-relation {
  color: #3498db;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 600;
}

/* Legend */
.graph-legend {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: rgba(26, 26, 26, 0.9);
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  max-width: 300px;
  z-index: 5;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  font-size: 0.7rem;
  color: #aaa;
  font-family: 'JetBrains Mono', monospace;
  white-space: nowrap;
}

/* Phase badge */
.phase-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  background: rgba(255, 69, 0, 0.15);
  border: 1px solid rgba(255, 69, 0, 0.3);
  color: #FF4500;
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Transitions */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(20px);
  opacity: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
