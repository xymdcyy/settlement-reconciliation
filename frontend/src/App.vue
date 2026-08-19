<template>
  <div id="app">
    <el-container style="min-height: 100vh;">
      <!-- 侧边导航 -->
      <el-aside width="220px" class="app-aside">
        <div class="app-logo">
          <h2>结算对账中心</h2>
        </div>
        <el-menu
          :default-active="currentRoute"
          router
          background-color="#001529"
          text-color="#ffffffa6"
          active-text-color="#fff"
        >
          <el-menu-item index="/upload">
            <el-icon><Upload /></el-icon>
            <span>上传对账单</span>
          </el-menu-item>
          <el-menu-item index="/workspace">
            <el-icon><DataBoard /></el-icon>
            <span>在线比对工作台</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <el-icon><Clock /></el-icon>
            <span>历史查询</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Upload, DataBoard, Clock } from '@element-plus/icons-vue'

const route = useRoute()
const currentRoute = computed(() => route.path)
</script>

<style scoped>
.app-aside {
  background-color: #001529;
  overflow: hidden;
}
.app-logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.app-logo h2 {
  color: #fff;
  font-size: 16px;
  margin: 0;
  white-space: nowrap;
}
.app-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>