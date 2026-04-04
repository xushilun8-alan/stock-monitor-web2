import axios from 'axios'

const BASE = '/api/stage-buying'

const api = axios.create({ baseURL: BASE })

// 获取股票列表
export function getStocks() {
  return api.get('/stocks').then(r => r.data)
}

// 获取单只股票详情
export function getStock(id) {
  return api.get(`/stocks/${id}`).then(r => r.data)
}

// 添加股票
export function addStock(data) {
  return api.post('/stocks', data).then(r => r.data)
}

// 更新股票
export function updateStock(id, data) {
  return api.put(`/stocks/${id}`, data).then(r => r.data)
}

// 删除股票
export function deleteStock(id) {
  return api.delete(`/stocks/${id}`).then(r => r.data)
}

// 批量导入
export function importStocks(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/stocks/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(r => r.data)
}

// 批量导出
export function exportStocks() {
  return api.get('/stocks/export', { responseType: 'blob' }).then(r => r.data)
}

// 刷新价格
export function refreshPrices() {
  return api.post('/stocks/refresh').then(r => r.data)
}

// 切换阶段执行状态
export function toggleStageExec(stageId) {
  return api.put(`/stages/${stageId}/exec`).then(r => r.data)
}

// 获取触发记录
export function getTriggerRecords(params = {}) {
  return api.get('/trigger-records', { params }).then(r => r.data)
}

// 获取配置
export function getConfig() {
  return api.get('/config').then(r => r.data)
}

// 更新配置
export function updateConfig(data) {
  return api.put('/config', data).then(r => r.data)
}

// 测试飞书通知
export function testFeishu() {
  return api.post('/config/feishu/test').then(r => r.data)
}

export default api
