<template>
  <el-drawer
    v-model="visibleProxy"
    :title="title"
    size="calc(100vw - 220px)"
    direction="rtl"
    append-to-body
    destroy-on-close
    :with-header="true"
    modal-class="omniqa-drawer-overlay"
    class="fullscreen-drawer"
  >
    <div class="fullscreen-body">
      <slot />
    </div>
    <template v-if="$slots.footer" #footer>
      <div class="fullscreen-footer">
        <slot name="footer" />
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
/**
 * frontend/src/components/common/FullScreenDrawer.vue
 *
 * 文件用途
 * -------
 * 全屏抽屉的统一封装组件（交互/视觉规范入口）。
 *
 * 设计目标：
 * - 全局所有“创建/编辑”型交互统一为全屏抽屉（size=100%）
 * - 统一 append-to-body，避免在列表区域高度不足时被裁剪
 * - 统一 body/footer 的 padding 与布局，让不同页面的抽屉风格一致
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

const visibleProxy = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})
</script>

<style scoped>
.fullscreen-body {
  height: calc(100vh - 110px);
  overflow: auto;
  padding: 18px 22px;
}
.fullscreen-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 22px;
  border-top: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}
</style>

<style>
/* 让抽屉“全屏但不覆盖左侧菜单”：菜单宽度当前固定 220px（MainLayout.vue）。 */
.omniqa-drawer-overlay {
  left: 220px !important;
  width: calc(100% - 220px) !important;
}
</style>
