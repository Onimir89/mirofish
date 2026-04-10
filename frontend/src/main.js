import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import en from '../locales/en.json'
import zh from '../locales/zh.json'

const savedLocale = localStorage.getItem('mirofish-locale') || 'en'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages: { en, zh },
})

const app = createApp(App)
app.use(router)
app.use(i18n)
app.mount('#app')
