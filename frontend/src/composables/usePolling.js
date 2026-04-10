import { ref, onBeforeUnmount } from 'vue'

export function usePolling(fn, intervalMs = 2000) {
  const isPolling = ref(false)
  let timer = null

  function start() {
    if (timer) return
    isPolling.value = true
    fn()
    timer = setInterval(fn, intervalMs)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isPolling.value = false
  }

  onBeforeUnmount(() => stop())

  return { start, stop, isPolling }
}
