export function useMarkdown() {
  function escapeHtml(str) {
    if (!str) return ''
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
  }

  function renderMarkdown(text) {
    if (!text) return ''
    let html = text
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
    html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
    // Bold and italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Code
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
    html = html.replace(/`(.+?)`/g, '<code>$1</code>')
    // Lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Paragraphs — split on double newlines, wrap only non-block lines
    html = html.split(/\n\n+/).map(function (block) {
      const trimmed = block.trim()
      if (/^<(h[1-6]|ul|ol|pre|li|blockquote|table|div)[\s>]/i.test(trimmed)) return trimmed
      return trimmed ? '<p>' + trimmed + '</p>' : ''
    }).filter(Boolean).join('\n')
    return html
  }

  return { renderMarkdown, escapeHtml }
}
