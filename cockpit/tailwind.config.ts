import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        swarm: {
          bg: '#09090b',
          surface: '#121215',
          card: '#18181b',
          border: '#27272a',
          borderHover: '#3f3f46',
          text: '#f4f4f5',
          muted: '#a1a1aa',
          dim: '#71717a',
        },
        status: {
          pass: '#10b981',
          passBg: '#064e3b33',
          warn: '#f59e0b',
          warnBg: '#78350f33',
          fail: '#ef4444',
          failBg: '#7f1d1d33',
          running: '#3b82f6',
          runningBg: '#1e3a8a33',
          cached: '#06b6d4',
          fresh: '#a855f7',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
