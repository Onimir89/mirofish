import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001',
  timeout: 300000, // 5 minutes
  headers: {
    'Accept': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const locale = localStorage.getItem('mirofish-locale') || 'en'
  config.headers['Accept-Language'] = locale
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message
    const status = error.response?.status || null

    if (import.meta.env.DEV) {
      console.error(`[API Error] ${status ?? 'network'}: ${message}`)
    }

    return Promise.reject({ message, status, original: error })
  },
)

export default apiClient
