import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'
import { validatePublicEnvironment } from './src/utils/apiConfig.js'

export default defineConfig(({ command, mode }) => {
  const root = fileURLToPath(new URL('.', import.meta.url))
  validatePublicEnvironment(loadEnv(mode, root, 'VITE_'), command === 'build')
  return { plugins: [react(), tailwindcss()] }
})
