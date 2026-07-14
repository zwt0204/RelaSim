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
    path: '/relasim',
    redirect: '/'
  },
  {
    path: '/relasim/run/:taskId',
    name: 'RelaSimRun',
    component: RelaSimReportView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
