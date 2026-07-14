import { createRouter, createWebHistory } from 'vue-router'
import RelaSimView from '../views/RelaSimView.vue'
import RelaSimReportView from '../views/RelaSimReportView.vue'

const routes = [
  {
    path: '/',
    name: 'RelaSim',
    component: RelaSimView
  },
  {
    path: '/run/:taskId',
    name: 'RelaSimRun',
    component: RelaSimReportView,
    props: true
  }
]

const router = createRouter({
  // base 取自 vite 的 base（/relasim/），最终 URL 形如 zwt.qzz.io/relasim/run/<id>
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
