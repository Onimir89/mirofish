import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: () => import('@/views/ProcessView.vue'),
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: () => import('@/views/SimulationView.vue'),
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: () => import('@/views/SimulationRunView.vue'),
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: () => import('@/views/ReportView.vue'),
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: () => import('@/views/InteractionView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
