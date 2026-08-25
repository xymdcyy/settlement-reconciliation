<template>
  <div id="app">
    <!-- v2.0 布局：纯内容容器，导航由各页面内部（工作台/返回按钮/系统管理入口）承载 -->
    <router-view />
  </div>
</template>

<script setup>
// v2.0 采用工作台为中心的导航，无全局侧边栏。
// 路由：/ 工作台、/customer/:id 客户详情、/admin 系统管理、/migration 数据迁移
</script>

<style>
#app {
  min-height: 100vh;
  background-color: #f0f2f5;
}
</style>