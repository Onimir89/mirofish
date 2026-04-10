import { ref, computed } from 'vue'

export function useStatus(initialClass = 'idle', initialLabel = 'Idle') {
  const statusClass = ref(initialClass)
  const statusLabel = ref(initialLabel)

  function update(cls, label) {
    statusClass.value = cls
    statusLabel.value = label
  }

  const dotClass = computed(() => `status-dot ${statusClass.value}`)

  return { statusClass, statusLabel, update, dotClass }
}
