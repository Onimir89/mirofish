<template>
  <div class="lang-switcher">
    <button
      :class="{ active: locale === 'en' }"
      @click="switchLang('en')"
    >
      EN
    </button>
    <button
      :class="{ active: locale === 'zh' }"
      @click="switchLang('zh')"
    >
      ZH
    </button>
  </div>
</template>

<script>
import { useI18n } from 'vue-i18n'

export default {
  name: 'LanguageSwitcher',
  setup() {
    const { locale } = useI18n({ useScope: 'global' })

    const switchLang = (lang) => {
      locale.value = lang
      localStorage.setItem('mirofish-locale', lang)
    }

    return { locale, switchLang }
  },
}
</script>

<style scoped>
.lang-switcher {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  gap: 0.25rem;
}

.lang-switcher button {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 0.25rem 0.5rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  cursor: pointer;
  border-radius: 3px;
  transition: all 0.2s;
}

.lang-switcher button.active {
  color: var(--accent);
  border-color: var(--accent);
}

.lang-switcher button:hover {
  border-color: var(--text-secondary);
}
</style>
