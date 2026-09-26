<template>
  <section class="page" data-module="roadcheck">
    <header class="page-head">
      <div>
        <h2>途中核查管理</h2>
        <p class="page-desc">核查弹窗、列表与详情共读同一条核查记录：温度记录与封签状态只跟着核查编号走，已归档记录只能查看。</p>
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <template v-if="!isArchived(row)">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="openCheck(action, row)"
              >
                {{ action }}
              </button>
              <button class="link" type="button" @click="openEdit(row)">修改记录</button>
              <button class="link" type="button" @click="archiveRow(row)">归档</button>
            </template>
            <span v-else class="archived-tag">已归档，只读</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无途中核查数据，可先登记途中核查</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条途中核查记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="dialogVisible" class="modal-mask" @click.self="closeDialog">
      <div class="modal-panel">
        <header class="modal-head">
          <h3>{{ dialogTitle }}</h3>
          <button class="link" type="button" @click="closeDialog">关闭</button>
        </header>

        <template v-if="dialogMode === 'detail'">
          <dl class="detail-grid">
            <template v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ form[column] ?? '—' }}</dd>
            </template>
          </dl>
          <p v-if="isArchived(form)" class="archived-tip">该核查记录已归档，只能查看，不能再修改。</p>
        </template>

        <form v-else class="modal-form" @submit.prevent="submitDialog">
          <template v-if="dialogMode === 'create'">
            <label class="form-item">
              <span>核查编号</span>
              <input v-model="form['核查编号']" required placeholder="唯一编号，温度与封签都挂在它下面" />
            </label>
            <label class="form-item">
              <span>关联调度</span>
              <input v-model="form['关联调度']" required placeholder="同一调度的历史核查会自动归档" />
            </label>
          </template>
          <label class="form-item">
            <span>核查时间</span>
            <input v-model="form['核查时间']" required />
          </label>
          <label class="form-item">
            <span>位置定位</span>
            <input v-model="form['位置定位']" />
          </label>
          <label class="form-item">
            <span>温度记录</span>
            <input v-model="form['温度记录']" placeholder="按实际读数填写" />
          </label>
          <label class="form-item">
            <span>封签状态</span>
            <select v-model="form['封签状态']">
              <option value="完好">完好</option>
              <option value="已拆封">已拆封</option>
            </select>
          </label>
          <label class="form-item">
            <span>核查人员</span>
            <input v-model="form['核查人员']" />
          </label>
          <footer class="modal-foot">
            <button class="btn primary" type="submit" :disabled="saving">{{ submitLabel }}</button>
            <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          </footer>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>
type DialogMode = 'create' | 'check' | 'edit' | 'detail'

const ENDPOINT = '/api/roadcheck'
const columns = ["核查编号", "关联调度", "核查时间", "位置定位", "温度记录", "封签状态", "核查人员", "核查状态"]
const actions = ["执行核查", "登记温度异常", "登记封签异常"]
const statuses = ["待核查", "已核查", "温度异常", "封签异常", "已归档"]
const editableFields = ["核查时间", "位置定位", "温度记录", "封签状态", "核查人员"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref({ keyword: '', status: '' })

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('detail')
const dialogAction = ref('')
const form = ref<Row>({})
const saving = ref(false)

const stats = computed(() => [
  { label: '待核查记录', value: countByStatus('待核查') },
  { label: '温度异常记录', value: countByStatus('温度异常') },
  { label: '封签异常记录', value: countByStatus('封签异常') },
])

const dialogTitle = computed(() => {
  const code = form.value['核查编号'] ?? ''
  if (dialogMode.value === 'create') return '登记途中核查'
  if (dialogMode.value === 'edit') return `修改核查记录 ${code}`
  if (dialogMode.value === 'check') return `${dialogAction.value} ${code}`
  return `核查详情 ${code}`
})

const submitLabel = computed(() => {
  if (dialogMode.value === 'check') return `确认${dialogAction.value}`
  if (dialogMode.value === 'create') return '登记'
  return '保存'
})

function countByStatus(status: string) {
  return rows.value.filter((row) => row['核查状态'] === status).length
}

function isArchived(row: Row) {
  return row['核查状态'] === '已归档'
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function fetchEntry(id: unknown): Promise<Row> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) {
    throw new Error('核查记录读取失败，请刷新后重试')
  }
  return (await response.json()) as Row
}

async function openDialog(mode: DialogMode, row: Row, action = '') {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    // 弹窗不沿用列表里的旧行，打开时实时读这条核查编号的记录
    form.value = await fetchEntry(row.id)
    dialogMode.value = mode
    dialogAction.value = action
    dialogVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '核查记录读取失败'
  }
}

function openCheck(action: string, row: Row) {
  void openDialog('check', row, action)
}

function openEdit(row: Row) {
  void openDialog('edit', row)
}

function openDetail(row: Row) {
  void openDialog('detail', row)
}

function openCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  form.value = { 封签状态: '完好' }
  dialogMode.value = 'create'
  dialogAction.value = ''
  dialogVisible.value = true
}

function closeDialog() {
  dialogVisible.value = false
}

function pickEditable(): Row {
  const values: Row = {}
  for (const field of editableFields) {
    if (form.value[field] !== undefined) {
      values[field] = form.value[field]
    }
  }
  return values
}

async function submitDialog() {
  saving.value = true
  errorMessage.value = ''
  try {
    let response: Response
    if (dialogMode.value === 'create') {
      const values: Row = {
        核查编号: form.value['核查编号'],
        关联调度: form.value['关联调度'],
        ...pickEditable(),
      }
      response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
    } else if (dialogMode.value === 'check') {
      // 核查动作与弹窗字段一次提交，温度记录、封签状态都落在同一条核查编号下
      const values: Row = { action: dialogAction.value, ...pickEditable() }
      response = await request(`${ENDPOINT}/${form.value.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ values }),
      })
    } else {
      response = await request(`${ENDPOINT}/${form.value.id}`, {
        method: 'PUT',
        body: JSON.stringify({ values: pickEditable() }),
      })
    }
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message || result.detail || '途中核查操作未生效，请稍后重试')
    }
    noticeMessage.value = result.message || '途中核查已保存'
    dialogVisible.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '途中核查操作失败'
  } finally {
    saving.value = false
  }
}

async function archiveRow(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '归档核查' } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message || '归档未生效，请稍后重试')
    }
    noticeMessage.value = result.message || '途中核查已归档'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '途中核查归档失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.status) query.set('status', filters.value.status)
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
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 420px;
  max-height: 80vh;
  overflow: auto;
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
.modal-form .form-item {
  display: block;
  margin-bottom: 10px;
}
.modal-form .form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.modal-form input,
.modal-form select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
}
.modal-foot {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.archived-tag {
  color: var(--muted);
  font-size: 12px;
}
.archived-tip {
  color: var(--muted);
  font-size: 12px;
  margin: 12px 0 0;
}
.notice-text {
  color: #067647;
}
</style>
