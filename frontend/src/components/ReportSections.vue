<template>
  <div class="sections-list">
    <div
      v-for="(section, i) in sections"
      :key="section.id || i"
      class="report-section"
    >
      <div class="section-header" @click="$emit('toggle-section', i)">
        <span class="section-toggle">{{ expandedSections[i] ? '&#9660;' : '&#9654;' }}</span>
        <h2 class="section-title">{{ section.title }}</h2>
      </div>
      <transition name="collapse">
        <div v-if="expandedSections[i]" class="section-body">
          <div class="section-content" v-html="renderMarkdown(section.content)"></div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script>
import { useMarkdown } from '@/composables/useMarkdown'

export default {
  name: 'ReportSections',
  props: {
    sections: {
      type: Array,
      required: true,
    },
    expandedSections: {
      type: Object,
      required: true,
    },
  },
  emits: ['toggle-section'],
  setup() {
    const { renderMarkdown } = useMarkdown()
    return { renderMarkdown }
  },
}
</script>

<style scoped>
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.report-section {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: background 0.15s;
}

.section-header:hover {
  background: #1f1f1f;
}

.section-toggle {
  color: #555;
  font-size: 0.7rem;
  width: 16px;
  text-align: center;
}

.section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  color: #e0e0e0;
  margin: 0;
}

.section-body {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid #2a2a2a;
}

.section-content {
  font-size: 0.85rem;
  color: #bbb;
  line-height: 1.7;
  padding-top: 1rem;
}

.section-content :deep(h2) {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.1rem;
  color: #e0e0e0;
  margin: 1.25rem 0 0.5rem;
}

.section-content :deep(h3) {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  color: #ccc;
  margin: 1rem 0 0.4rem;
}

.section-content :deep(h4) {
  font-size: 0.9rem;
  color: #bbb;
  margin: 0.75rem 0 0.3rem;
}

.section-content :deep(strong) { color: #e0e0e0; }
.section-content :deep(em) { color: #aaa; }

.section-content :deep(code) {
  background: #111;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85em;
  color: #FF4500;
}

.section-content :deep(pre) {
  background: #000;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 1rem;
  overflow-x: auto;
  margin: 0.75rem 0;
}

.section-content :deep(pre code) {
  background: none;
  padding: 0;
  color: #00ff00;
}

.section-content :deep(ul) {
  padding-left: 1.25rem;
  margin: 0.5rem 0;
}

.section-content :deep(li) {
  margin: 0.25rem 0;
}

/* Collapse transition */
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.25s ease;
  max-height: 2000px;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
