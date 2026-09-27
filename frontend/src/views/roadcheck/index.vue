<template>
  <section class="page" data-module="roadcheck">
    <header class="page-head">
      <div>
        <h2>途中核查管理</h2>
        <p class="page-desc">维护途中核查，围绕核查编号、关联调度、核查时间、位置定位做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记途中核查</button>
        <button class="btn" type="button" @click="exportRows">导出途中核查清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>核查编号</span>
        <input v-model="filters.keyword" placeholder="按核查编号检索" />
      </label>
      <label class="filter-item">
        <span>关联调度</span>
        <input v-model="filters.dispatch" placeholder="按关联调度检索" />
      </label>
      <label class="filter-item">
        <span>核查状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            {{ column === '核查状态' ? statusOf(row) : (row[column] ?? '—') }}
          </td>
          <td class="row-actions">
            <template v-if="row.archived">
              <button class="link" type="button" @click="openDetail(row)">查看</button>
              <span class="archived-tag">已归档</span>
            </template>
            <template v-else>
              <button class="link" type="button" @click="openEdit(row)">核查登记</button>
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无途中核查数据，可先登记途中核查</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条途中核查记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="dialog.visible" class="modal-mask" @click.self="closeDialog">
      <div class="modal-card" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>{{ dialogTitle }}</h3>
          <button class="link" type="button" @click="closeDialog">关闭</button>
        </header>

        <div v-if="dialog.loading" class="modal-body">正在读取核查记录…</div>
        <div v-else class="modal-body">
          <template v-if="dialog.mode !== 'create'">
            <label class="form-item">
              <span>核查编号</span>
              <input :value="dialog.form.核查编号" disabled />
            </label>
            <label class="form-item">
              <span>关联调度</span>
              <input :value="dialog.form.关联调度" disabled />
            </label>
          </template>
          <template v-else>
            <label class="form-item">
              <span>核查编号 *</span>
              <input v-model="dialog.form.核查编号" placeholder="同一趟运输的再次核查请用新编号" />
            </label>
            <label class="form-item">
              <span>关联调度 *</span>
              <input v-model="dialog.form.关联调度" placeholder="如 DISP-0001" />
            </label>
          </template>

          <label class="form-item">
            <span>核查时间 {{ dialog.mode === 'create' ? '*' : '' }}</span>
            <input v-model="dialog.form.核查时间" :disabled="dialog.readonly" placeholder="如 2026-09-27 10:30" />
          </label>
          <label class="form-item">
            <span>位置定位</span>
            <input v-model="dialog.form.位置定位" :disabled="dialog.readonly" />
          </label>
          <label class="form-item">
            <span>温度记录</span>
            <input v-model="dialog.form.温度记录" :disabled="dialog.readonly" placeholder="如 -18.2℃" />
          </label>
          <label class="form-item">
            <span>封签状态</span>
            <select v-model="dialog.form.封签状态" :disabled="dialog.readonly">
              <option value="">未登记</option>
              <option v-for="option in sealOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>核查人员</span>
            <input v-model="dialog.form.核查人员" :disabled="dialog.readonly" />
          </label>

          <p v-if="dialog.readonly" class="modal-tip">该记录已归档，仅可查询，不能再修改。</p>
          <p v-if="dialog.error" class="error-text">{{ dialog.error }}</p>
        </div>

        <footer class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button
            v-if="!dialog.readonly"
            class="btn primary"
            type="button"
            :disabled="dialog.saving"
            @click="saveDialog"
          >
            {{ dialog.saving ? '保存中…' : '保存核查结果' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null | undefined>

const ENDPOINT = '/api/roadcheck'
const columns = ["核查编号", "关联调度", "核查时间", "位置定位", "温度记录", "封签状态", "核查人员", "核查状态"]
const actions = ["执行核查", "登记温度异常", "登记封签异常", "归档"]
const statuses = ["待核查", "已核查", "温度异常", "封签异常"]
const sealOptions = ["完好", "已拆封", "破损"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', dispatch: '', status: '' })

const dialog = reactive({
  visible: false,
  loading: false,
  saving: false,
  readonly: false,
  mode: 'edit' as 'edit' | 'create',
  entryId: null as number | null,
  error: '',
  form: {
    核查编号: '',
    关联调度: '',
    核查时间: '',
    位置定位: '',
    温度记录: '',
    封签状态: '',
    核查人员: '',
  } as Record<string, string>,
})

const dialogTitle = computed(() => {
  if (dialog.mode === 'create') return '登记途中核查'
  return dialog.readonly ? `核查详情（已归档） ${dialog.form.核查编号}` : `核查登记 ${dialog.form.核查编号}`
})

const stats = computed(() => [
  { label: '待核查记录', value: rows.value.filter((row) => row.status === '待核查').length },
  { label: '温度异常记录', value: rows.value.filter((row) => row.status === '温度异常').length },
  { label: '封签异常记录', value: rows.value.filter((row) => row.status === '封签异常').length },
])

function statusOf(row: Row): string {
  const status = typeof row.status === 'string' ? row.status : ''
  return status || String(row['核查状态'] ?? '—')
}

function resetFilters() {
  filters.value = { keyword: '', dispatch: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  dialog.mode = 'create'
  dialog.readonly = false
  dialog.entryId = null
  dialog.error = ''
  Object.keys(dialog.form).forEach((key) => { dialog.form[key] = '' })
  dialog.visible = true
}

function openDialogWith(row: Row, readonly: boolean) {
  dialog.mode = 'edit'
  dialog.readonly = readonly
  dialog.entryId = Number(row.id)
  dialog.error = ''
  dialog.visible = true
  dialog.loading = true
  // 弹窗与列表读同一份后端数据：打开时重新拉取该核查编号的最新记录
  request(`${ENDPOINT}/${dialog.entryId}`)
    .then(async (response) => {
      if (!response.ok) throw new Error('核查记录读取失败')
      const entry = (await response.json()) as Row
      ;['核查编号', '关联调度', '核查时间', '位置定位', '温度记录', '封签状态', '核查人员'].forEach((field) => {
        dialog.form[field] = entry[field] == null ? '' : String(entry[field])
      })
      dialog.readonly = readonly || Boolean(entry.archived)
    })
    .catch((error: unknown) => {
      dialog.error = error instanceof Error ? error.message : '核查记录读取失败'
    })
    .finally(() => {
      dialog.loading = false
    })
}

function openEdit(row: Row) {
  openDialogWith(row, false)
}

function openDetail(row: Row) {
  openDialogWith(row, true)
}

function closeDialog() {
  dialog.visible = false
}

async function saveDialog() {
  dialog.error = ''
  dialog.saving = true
  try {
    const isCreate = dialog.mode === 'create'
    const response = await request(isCreate ? ENDPOINT : `${ENDPOINT}/${dialog.entryId}`, {
      method: isCreate ? 'POST' : 'PUT',
      body: JSON.stringify({ values: { ...dialog.form } }),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '核查结果保存失败，请稍后重试')
    }
    dialog.visible = false
    await reload()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '核查结果保存失败'
  } finally {
    dialog.saving = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '途中核查动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '途中核查操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  Object.entries(filters.value).forEach(([key, value]) => {
    if (value) query.set(key, value)
  })
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('途中核查列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '途中核查列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  border: 1px solid var(--border);
  padding: 16px 18px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.modal-head h3 {
  margin: 0;
  font-size: 15px;
}
.modal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  background: #fff;
}
.form-item input:disabled,
.form-item select:disabled {
  background: #f1f5f9;
  color: var(--muted);
}
.modal-tip {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.archived-tag {
  font-size: 12px;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
}
.filter-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 13px;
  background: #fff;
}
</style>
