<template>
  <div class="reconciliation-tab">
    <el-card>
      <template #header>
        <span>对账核对</span>
      </template>
      <p>核对功能开发中（复用现有引擎）...</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  customerId: {
    type: Number,
    required: true
  }
})
</script>

<style scoped>
.reconciliation-tab {
  padding: 20px 0;
}
</style>
