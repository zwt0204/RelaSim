import service, { requestWithRetry } from './index'

/**
 * 启动一次关系推演（异步，返回 task_id）
 * @param {Object} data - { seed_material, prediction_query, rounds, time_unit, events }
 * @returns {Promise}
 */
export function runRelaSim(data) {
  return service({
    url: '/api/relasim/run',
    method: 'post',
    data
  })
}

/**
 * 查询推演任务进度
 * @param {String} taskId
 * @returns {Promise}
 */
export function getRelaSimStatus(taskId) {
  return service({
    url: '/api/relasim/run/status',
    method: 'get',
    params: { task_id: taskId }
  })
}

/**
 * 获取已完成推演的完整结果（图谱 + 仿真 + 报告）
 * @param {String} relasimId
 * @returns {Promise}
 */
export function getRelaSimResult(relasimId) {
  return requestWithRetry(() =>
    service({
      url: `/api/relasim/${relasimId}`,
      method: 'get'
    })
  )
}

/**
 * 与推演中的某位当事人对话
 * @param {Object} data - { relasim_id, person_id, message, history }
 * @returns {Promise}
 */
export function chatWithPerson(data) {
  return service({
    url: '/api/relasim/chat',
    method: 'post',
    data
  })
}

/**
 * 历史推演列表
 * @param {Number} limit
 * @returns {Promise}
 */
export function getRelaSimHistory(limit = 20) {
  return service({
    url: '/api/relasim/history',
    method: 'get',
    params: { limit }
  })
}
