import { ref } from 'vue'

export function useApi() {
  const loading = ref(false)
  const error = ref(null)

  async function execute(apiFn, ...args) {
    loading.value = true
    error.value = null
    try {
      const result = await apiFn(...args)
      return result
    } catch (e) {
      error.value = e.message || String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  return { loading, error, execute }
}
