/*
 * frontend/vite.config.js
 *
 * 文件用途
 * -------
 * Vite 构建与开发服务器配置。
 *
 * 关键职责：
 * 1. 注册 Vue 插件，让 `.vue` 单文件组件可以被正确编译。
 * 2. 规定前端开发服务器端口为 `5173`。
 * 3. 配置开发期反向代理：
 *    - `/api` 转发到 Django 后端 `127.0.0.1:8000`
 *    - `/reports` 转发到 Django 报告静态目录
 *
 * 这样前端开发时无需关心跨域与后端真实地址，页面直接请求相对路径即可。
 */

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/reports': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
