<template>
  <section>
    <div class="page-head">
      <h1 class="page-title">质量驾驶舱</h1>
      <el-button @click="load">刷新</el-button>
    </div>

    <div class="metrics">
      <div class="metric">
        <span>今日通过率</span>
        <strong>{{ metrics.today_pass_rate }}%</strong>
        <em>{{ metrics.today_tasks }} 个任务</em>
      </div>
      <div class="metric">
        <span>本周通过率</span>
        <strong>{{ metrics.week_pass_rate }}%</strong>
        <em>{{ metrics.week_tasks }} 个任务</em>
      </div>
      <div class="metric danger">
        <span>本周失败任务</span>
        <strong>{{ metrics.failed_tasks_week }}</strong>
        <em>优先处理失败诊断</em>
      </div>
      <div class="metric">
        <span>定时任务健康</span>
        <strong>{{ scheduleOk }}/{{ schedule.enabled || 0 }}</strong>
        <em>{{ schedule.overdue }} 个已超时</em>
      </div>
      <div class="metric">
        <span>环境配置</span>
        <strong>{{ environment.configured }}/{{ environment.total }}</strong>
        <em>{{ environment.missing_base_url }} 个缺少 base_url</em>
      </div>
      <div class="metric warning">
        <span>无断言资产</span>
        <strong>{{ governance.no_assertion_cases }}</strong>
        <em>接口用例 + 场景步骤</em>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <div class="panel-title">最近失败趋势</div>
        <el-table :data="quality.trend" size="small">
          <el-table-column prop="date" label="日期" />
          <el-table-column prop="total" label="任务" width="70" />
          <el-table-column prop="passed" label="通过" width="70" />
          <el-table-column prop="failed" label="失败" width="70" />
          <el-table-column label="通过率" width="100">
            <template #default="{ row }">{{ row.pass_rate }}%</template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-title">失败最多的模块</div>
        <el-table :data="quality.failed_modules" size="small">
          <el-table-column prop="case__api__module__name" label="模块" />
          <el-table-column prop="failed_count" label="失败次数" width="100" />
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-title">失败最多的接口</div>
        <el-table :data="quality.failed_interfaces" size="small">
          <el-table-column label="接口">
            <template #default="{ row }">
              <span class="method">{{ row.case__api__method }}</span> {{ row.case__api__path }}
            </template>
          </el-table-column>
          <el-table-column prop="failed_count" label="失败" width="80" />
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-title">失败原因分布（近 7 天）</div>
        <el-table :data="quality.failure_categories" size="small">
          <el-table-column prop="failure_category" label="分类" />
          <el-table-column prop="count" label="次数" width="90" />
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-title">最慢接口 Top 5（近 7 天）</div>
        <el-table :data="quality.slow_interfaces" size="small">
          <el-table-column label="接口">
            <template #default="{ row }">
              <span class="method">{{ row.case__api__method }}</span> {{ row.case__api__path }}
            </template>
          </el-table-column>
          <el-table-column prop="avg_duration_ms" label="平均(ms)" width="110" />
          <el-table-column prop="max_duration_ms" label="最慢(ms)" width="110" />
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-title">不稳定用例 Top 5</div>
        <el-table :data="quality.flaky_cases" size="small">
          <el-table-column prop="case_code" label="ID" width="110" />
          <el-table-column prop="title" label="用例" />
          <el-table-column label="失败率" width="90">
            <template #default="{ row }">{{ row.failure_rate }}%</template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel wide">
        <div class="panel-title">测试资产治理</div>
        <div class="governance">
          <span>长期未执行用例 <b>{{ governance.unexecuted_cases }}</b></span>
          <span>长期失败用例 <b>{{ governance.long_failed_cases }}</b></span>
          <span>无归属场景 <b>{{ governance.no_module_scenarios }}</b></span>
          <span>疑似重复接口 <b>{{ governance.duplicate_interfaces }}</b></span>
        </div>
      </div>

      <div class="panel wide">
        <div class="panel-title">模块覆盖率</div>
        <el-table :data="quality.coverage" size="small">
          <el-table-column prop="project" label="项目" width="140" />
          <el-table-column prop="module" label="模块" />
          <el-table-column prop="api_count" label="接口数" width="90" />
          <el-table-column prop="covered_api_count" label="已覆盖" width="90" />
          <el-table-column label="覆盖率" width="180">
            <template #default="{ row }">
              <el-progress :percentage="row.coverage_rate" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 质量驾驶舱首页，集中展示接口测试平台的核心度量，如通过率、失败趋势、环境健康度、治理指标与覆盖率。
 * 2. 该页面依赖 dashboardApi 拉取聚合统计结果，是登录后进入 MainLayout 后的总览入口，用于辅助测试运营和问题定位。
 * 3. 页面只负责可视化展示后端汇总数据，不维护复杂编辑状态，也不会直接修改测试资产。
 */
import { computed, onMounted, ref } from 'vue'
import { dashboardApi } from '../api/resources'

const quality = ref({
  metrics: {},
  trend: [],
  failed_modules: [],
  failed_interfaces: [],
  failure_categories: [],
  slow_interfaces: [],
  flaky_cases: [],
  schedule_health: {},
  environment_health: {},
  governance: {},
  coverage: []
})

const metrics = computed(() => quality.value.metrics || {})
const schedule = computed(() => quality.value.schedule_health || {})
const environment = computed(() => quality.value.environment_health || {})
const governance = computed(() => quality.value.governance || {})
const scheduleOk = computed(() => Math.max((schedule.value.enabled || 0) - (schedule.value.overdue || 0), 0))

async function load() {
  quality.value = await dashboardApi.quality()
}

onMounted(load)
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.metric {
  min-height: 106px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.metric span,
.metric em {
  display: block;
  color: #64748b;
  font-style: normal;
}
.metric strong {
  display: block;
  margin: 8px 0 4px;
  font-size: 30px;
  line-height: 1;
}
.metric.danger strong {
  color: #dc2626;
}
.metric.warning strong {
  color: #d97706;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.wide {
  grid-column: span 2;
}
.panel-title {
  margin-bottom: 12px;
  font-weight: 700;
}
.method {
  display: inline-block;
  min-width: 46px;
  color: #2563eb;
  font-weight: 700;
}
.governance {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.governance span {
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #475569;
}
.governance b {
  display: block;
  margin-top: 6px;
  color: #111827;
  font-size: 22px;
}
@media (max-width: 1100px) {
  .metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .metrics,
  .grid,
  .governance {
    grid-template-columns: 1fr;
  }
  .wide {
    grid-column: auto;
  }
}
</style>
