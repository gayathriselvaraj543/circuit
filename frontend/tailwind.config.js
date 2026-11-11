/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0b1020',
        panel: '#111827',
        accent: '#60a5fa',
        muted: '#94a3b8',
      },
    },
  },
  plugins: [],
};
