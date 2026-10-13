import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const testTarget = process.env.ORTAK_TEST_BACKEND_URL
const proxy = testTarget ? { '/api': { target: testTarget, rewrite: (path) => path.replace(/^\/api/, '') } } : undefined

export default defineConfig({ plugins: [react()], server: { proxy }, preview: { proxy } })
