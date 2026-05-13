/**
 * frontend/src/main.js
 *
 * 文件用途
 * -------
 * 前端应用入口（Vite + Vue 3）。
 *
 * 负责完成：
 * - 创建 Vue App 实例并挂载到 index.html 的 #app
 * - 注册全局插件：Pinia（状态管理）、Vue Router（路由）、Element Plus（UI 组件）
 * - 引入全局样式：styles/global.css
 *
 * 面试讲解抓手
 * -----------
 * 这是“启动装配层”，不写业务逻辑；业务页面都在 views/，复用组件在 components/。
 */

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './styles/global.css'

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')
