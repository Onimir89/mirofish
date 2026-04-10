<template>
  <div class="view-shell">
    <!-- Top bar -->
    <header class="topbar">
      <router-link to="/" class="topbar-brand">
        <span class="brand-name">MiroFish</span>
        <span class="brand-sep">/</span>
        <span class="brand-context">{{ $t('interaction.context') }}</span>
      </router-link>
      <div class="topbar-status">
        <span class="status-dot success"></span>
        <span class="status-text">{{ $t('interaction.interactive') }}</span>
      </div>
    </header>

    <!-- Split layout -->
    <div class="split-layout">
      <!-- Left: Report (read-only) -->
      <div class="panel-left report-readonly-panel">
        <div v-if="report" class="report-readonly">
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

        <div v-else class="loading-placeholder">
          <div class="spinner-md"></div>
          <p>{{ $t('interaction.loading_report') }}</p>
        </div>
      </div>

      <!-- Right: Chat Interface -->
      <div class="panel-right chat-panel">
        <!-- Agent selector -->
        <div class="chat-toolbar">
          <div class="agent-selector">
            <label class="selector-label">{{ $t('interaction.chat_with') }}</label>
            <select v-model="selectedAgent" class="agent-dropdown">
              <option value="">{{ $t('interaction.report_agent') }}</option>
              <option
                v-for="agent in agents"
                :key="agent.id || agent.name"
                :value="agent.id || agent.name"
              >{{ agent.name }}</option>
            </select>
          </div>
        </div>

        <!-- Chat messages -->
        <div class="chat-messages" ref="chatRef">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="chat-message"
            :class="msg.role"
          >
            <div class="msg-avatar" v-if="msg.role === 'assistant'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
              </svg>
            </div>
            <div class="msg-bubble">
              <div class="msg-content" v-html="msg.role === 'assistant' ? renderMarkdown(msg.content) : escapeHtml(msg.content)"></div>
            </div>
            <div class="msg-avatar user-avatar" v-if="msg.role === 'user'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
          </div>

          <!-- Typing indicator -->
          <div v-if="typing" class="chat-message assistant">
            <div class="msg-avatar">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
              </svg>
            </div>
            <div class="msg-bubble typing-bubble">
              <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>

          <div v-if="!messages.length" class="chat-welcome">
            <div class="welcome-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="1.5">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
              </svg>
            </div>
            <h3>{{ $t('interaction.chat_title') }}</h3>
            <p>{{ $t('interaction.chat_hint') }}</p>
          </div>
        </div>

        <!-- Input area -->
        <div class="chat-input-area">
          <div class="input-wrapper">
            <textarea
              v-model="inputText"
              ref="inputRef"
              :placeholder="$t('interaction.chat_placeholder')"
              rows="1"
              @keydown.enter.exact.prevent="sendMessage"
              @input="autoResize"
            ></textarea>
            <button
              class="send-btn"
              :disabled="!inputText.trim() || typing"
              @click="sendMessage"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ReportSections from '@/components/ReportSections.vue'
import { getReport, getReportSections, chatWithReport } from '@/api/report'
import { getSimulationProfiles } from '@/api/simulation'
import { useMarkdown } from '@/composables/useMarkdown'

export default {
  name: 'InteractionView',
  components: { ReportSections },
  setup() {
    const route = useRoute()
    const { t } = useI18n()
    const reportId = route.params.reportId

    const report = ref(null)
    const sections = ref([])
    const expandedSections = ref({})
    const agents = ref([])
    const selectedAgent = ref('')
    const messages = ref([])
    const inputText = ref('')
    const typing = ref(false)
    const chatRef = ref(null)
    const inputRef = ref(null)

    const { renderMarkdown, escapeHtml } = useMarkdown()

    const toggleSection = (idx) => {
      expandedSections.value[idx] = !expandedSections.value[idx]
    }

    const scrollChat = async () => {
      await nextTick()
      if (chatRef.value) {
        chatRef.value.scrollTop = chatRef.value.scrollHeight
      }
    }

    const autoResize = () => {
      if (inputRef.value) {
        inputRef.value.style.height = 'auto'
        inputRef.value.style.height = Math.min(inputRef.value.scrollHeight, 120) + 'px'
      }
    }

    const sendMessage = async () => {
      const text = inputText.value.trim()
      if (!text || typing.value) return

      messages.value.push({ role: 'user', content: text })
      inputText.value = ''
      if (inputRef.value) inputRef.value.style.height = 'auto'
      typing.value = true
      await scrollChat()

      try {
        const res = await chatWithReport(reportId, text, selectedAgent.value || null)
        const reply = res.data.answer || 'No response.'
        messages.value.push({ role: 'assistant', content: reply })
      } catch (e) {
        messages.value.push({
          role: 'assistant',
          content: t('interaction.error_reply'),
        })
      } finally {
        typing.value = false
        await scrollChat()
      }
    }

    const loadData = async () => {
      try {
        const res = await getReport(reportId)
        report.value = res.data

        try {
          const secRes = await getReportSections(reportId)
          sections.value = Array.isArray(secRes.data) ? secRes.data : secRes.data.sections || []
        } catch (_) {
          if (report.value.sections) sections.value = report.value.sections
        }

        if (report.value.simulation_id) {
          try {
            const profRes = await getSimulationProfiles(report.value.simulation_id)
            agents.value = Array.isArray(profRes.data) ? profRes.data : profRes.data.profiles || []
          } catch (_) {}
        }
      } catch (e) {
        // Report not found - show empty state
      }
    }

    onMounted(() => {
      loadData()
    })

    onBeforeUnmount(() => {
      typing.value = false
    })

    return {
      report,
      sections,
      expandedSections,
      agents,
      selectedAgent,
      messages,
      inputText,
      typing,
      chatRef,
      inputRef,
      renderMarkdown,
      escapeHtml,
      toggleSection,
      sendMessage,
      autoResize,
    }
  },
}
</script>

<style scoped>
/* Left: Report */
.report-readonly-panel {
  overflow-y: auto;
  padding: 2rem 2.5rem;
}

.loading-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  height: 300px;
  color: #555;
}

/* Report readonly */
.report-readonly .report-title {
  font-family: var(--font-heading);
  font-size: 1.75rem;
  color: var(--text-primary);
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.report-summary {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.summary-content {
  font-size: 0.85rem;
  color: #ccc;
  line-height: 1.7;
}

.summary-content :deep(strong) { color: var(--text-primary); }
.summary-content :deep(code) {
  background: #111;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--accent);
}

/* Right: Chat */
.chat-panel {
  width: 440px;
  display: flex;
  flex-direction: column;
  background: #0e0e0e;
}

.chat-toolbar {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
}

.agent-selector {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.selector-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.agent-dropdown {
  flex: 1;
  padding: 0.4rem 0.75rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 0.8rem;
  font-family: var(--font-sans);
  cursor: pointer;
}

.agent-dropdown:focus {
  outline: none;
  border-color: var(--accent);
}

.agent-dropdown option {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* Chat messages */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.chat-message {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
  margin-top: 2px;
}

.user-avatar {
  background: rgba(255, 69, 0, 0.1);
  border-color: rgba(255, 69, 0, 0.2);
  color: var(--accent);
}

.msg-bubble {
  max-width: 85%;
  padding: 0.65rem 0.9rem;
  border-radius: 12px;
  font-size: 0.85rem;
  line-height: 1.6;
}

.assistant .msg-bubble {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: #ccc;
  border-top-left-radius: 4px;
}

.user .msg-bubble {
  background: rgba(255, 69, 0, 0.12);
  border: 1px solid rgba(255, 69, 0, 0.2);
  color: var(--text-primary);
  border-top-right-radius: 4px;
}

.msg-content :deep(strong) { color: var(--text-primary); }
.msg-content :deep(code) {
  background: #111;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--accent);
}

.msg-content :deep(pre) {
  background: #000;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem;
  overflow-x: auto;
  margin: 0.4rem 0;
}

.msg-content :deep(pre code) {
  background: none;
  padding: 0;
  color: #00ff00;
}

/* Typing indicator */
.typing-bubble {
  padding: 0.75rem 1rem;
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #555;
  animation: typingBounce 1.4s infinite;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

/* Welcome message */
.chat-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 0.5rem;
  padding: 2rem;
}

.chat-welcome h3 {
  font-family: var(--font-heading);
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 0;
}

.chat-welcome p {
  font-size: 0.8rem;
  color: #555;
  max-width: 280px;
  line-height: 1.5;
}

/* Input area */
.chat-input-area {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.5rem 0.5rem 0.5rem 1rem;
  transition: border-color 0.2s;
}

.input-wrapper:focus-within {
  border-color: var(--accent);
}

.input-wrapper textarea {
  flex: 1;
  background: none;
  border: none;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.85rem;
  resize: none;
  max-height: 120px;
  line-height: 1.5;
  padding: 0.2rem 0;
}

.input-wrapper textarea:focus {
  outline: none;
}

.input-wrapper textarea::placeholder {
  color: #444;
}

.send-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--accent);
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.send-btn:hover:not(:disabled) { opacity: 0.85; }
.send-btn:disabled { opacity: 0.3; cursor: not-allowed; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
}

@media (max-width: 768px) {
  .report-readonly-panel { padding: 1rem; max-height: 40vh; }
  .chat-panel { width: 100%; flex: 1; }
}
</style>
