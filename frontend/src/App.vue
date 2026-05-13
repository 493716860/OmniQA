<!--
  文件说明：
  1. 应用根组件，仅负责提供全局路由出口，是前端启动后的第一层渲染容器。
  2. 具体页面结构由 `src/router/index.js` 决定，
     登录态页面通常会进入 `src/layouts/MainLayout.vue`，
     再继续承载各业务视图。
  3. 该文件刻意保持轻量，不承担认证、菜单、数据请求等职责，便于将业务逻辑下沉到布局、stores 与 views。
-->
<template>
  <router-view />
</template>
