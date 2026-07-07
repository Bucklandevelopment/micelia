const preset = require('../../design-system/tailwind.preset.cjs')

/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [preset],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // Legacy token names kept, now REMAPPED to canonical design-system vars
      // (tokens.css) so existing idm-*/energy-* class usages adopt the look
      // without touching components.
      colors: {
        idm: {
          primary: 'var(--accent-cyan)',
          health: 'var(--accent-green)',
          education: 'var(--accent-yellow)',
          identity: 'var(--accent-red)',
          dark: 'var(--bg-secondary)',
          darker: 'var(--bg-primary)',
          surface: 'var(--bg-secondary)',
          border: 'var(--border)',
        },
        energy: {
          abundant: 'var(--accent-green)',
          normal: 'var(--accent-cyan)',
          conserving: 'var(--accent-yellow)',
          critical: 'var(--accent-red)',
          survival: 'var(--accent-red)',
        },
      },
    },
  },
  plugins: [],
}
