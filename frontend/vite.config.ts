import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Vite would otherwise build happily without this, and the deployed app
  // would call "/auth/me" on the frontend's own host and fail in confusing ways.
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  if (mode === 'production' && !env.VITE_API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL must be set for a production build.')
  }

  return {
    plugins: [react()],
    test: {
      environment: 'jsdom',
    },
  }
})
