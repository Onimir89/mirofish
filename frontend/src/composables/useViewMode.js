import { ref } from 'vue'

export function useViewMode(defaultMode = 'split') {
  const viewMode = ref(defaultMode)  // 'graph' | 'split' | 'workbench'

  const setMode = (mode) => { viewMode.value = mode }
  const isGraphVisible = () => viewMode.value !== 'workbench'
  const isWorkbenchVisible = () => viewMode.value !== 'graph'

  return { viewMode, setMode, isGraphVisible, isWorkbenchVisible }
}
