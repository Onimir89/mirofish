<template>
  <div id="mirofish-app">
    <router-view />
  </div>
</template>

<script>
export default {
  name: 'App',
}
</script>

<style>
@import '@/assets/layout.css';

*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #0a0a0a;
  --bg-secondary: #1a1a1a;
  --bg-card: #1a1a1a;
  --text-primary: #e0e0e0;
  --text-secondary: #888;
  --accent: #FF4500;
  --accent-dim: #cc3700;
  --danger: #DC143C;
  --success: #2E8B57;
  --border: #2a2a2a;
  --font-heading: 'Space Grotesk', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-sans);
  min-height: 100vh;
}

#mirofish-app {
  min-height: 100vh;
}

a {
  color: var(--accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

code, pre {
  font-family: var(--font-mono);
}
</style>
