<template>
  <div class="relasim-report-page">
    <nav class="navbar">
      <div class="nav-brand" @click="goHome">MIROFISH<span class="brand-suffix">/ RELASIM</span></div>
      <div class="nav-links">
        <LanguageSwitcher />
        <span class="nav-divider">|</span>
        <span class="nav-back" @click="newRun">{{ $t('relasim.backToInput') }} ↗</span>
      </div>
    </nav>

    <div class="main-content">
      <!-- 加载态 -->
      <div v-if="phase === 'loading'" class="loading-state">
        <div class="loading-tag">◇ {{ $t('relasim.loadingTitle') }}</div>
        <h1 class="loading-title">SIMULATING<span class="cursor">_</span></h1>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="progress-meta">
          <span class="progress-pct">{{ progress }}%</span>
          <span class="progress-msg">{{ statusMsg }}</span>
        </div>
        <p class="loading-hint">{{ $t('relasim.loadingHint') }}</p>
      </div>

      <!-- 错误态 -->
      <div v-else-if="phase === 'error'" class="error-state">
        <div class="error-tag">✕ ERROR</div>
        <h1 class="error-title">{{ $t('relasim.errorRun') }}</h1>
        <pre class="error-detail">{{ errorMsg }}</pre>
        <button class="retry-btn" @click="newRun">{{ $t('relasim.backToInput') }} →</button>
      </div>

      <!-- 报告态 -->
      <div v-else-if="phase === 'report' && data" class="report-body">
        <!-- 标题 -->
        <header class="report-header">
          <div class="header-tag">◇ {{ $t('relasim.reportTitle') }}</div>
          <h1 class="report-title">{{ $t('relasim.reportTitle') }}</h1>
          <p class="report-context" v-if="data.graph && data.graph.context">{{ data.graph.context }}</p>
        </header>

        <!-- 参与的人 -->
        <section class="block" v-if="data.graph && data.graph.persons">
          <div class="block-meta"><span class="block-num">01</span><span class="block-name">{{ $t('relasim.sectionPersons') }}</span></div>
          <div class="persons-grid">
            <div v-for="p in data.graph.persons" :key="p.person_id" class="person-card">
              <div class="person-head">
                <span class="person-avatar" :class="p.gender">{{ (p.name || '?').slice(0,1) }}</span>
                <div class="person-id">
                  <div class="person-name">{{ p.name }}</div>
                  <div class="person-sub">{{ p.gender === 'female' ? '♀' : p.gender === 'male' ? '♂' : '·' }} {{ p.age || '—' }}</div>
                </div>
                <span class="attach-badge" :class="p.attachment_style">{{ attachLabel(p.attachment_style) }}</span>
              </div>
              <div class="person-fields">
                <div class="pf"><span class="pf-k">性格</span><span class="pf-v">{{ p.personality || '—' }}</span></div>
                <div class="pf"><span class="pf-k">情感需求</span><span class="pf-v">{{ p.emotional_needs || '—' }}</span></div>
                <div class="pf"><span class="pf-k">雷区</span><span class="pf-v">{{ p.triggers || '—' }}</span></div>
              </div>
            </div>
          </div>
        </section>

        <!-- 可能的结局 -->
        <section class="block" v-if="data.report && data.report.outcomes">
          <div class="block-meta"><span class="block-num">02</span><span class="block-name">{{ $t('relasim.sectionOutcomes') }}</span></div>
          <div class="outcomes">
            <div v-for="(o, i) in sortedOutcomes" :key="i" class="outcome-row">
              <div class="outcome-bar-wrap">
                <div class="outcome-bar" :style="{ width: (o.probability * 100) + '%' }"></div>
              </div>
              <div class="outcome-info">
                <div class="outcome-top">
                  <span class="outcome-label">{{ o.label }}</span>
                  <span class="outcome-pct">{{ Math.round(o.probability * 100) }}%</span>
                </div>
                <p class="outcome-rationale" v-if="o.rationale">{{ o.rationale }}</p>
              </div>
            </div>
          </div>
        </section>

        <!-- 情感变化曲线 -->
        <section class="block" v-if="hasCurves">
          <div class="block-meta"><span class="block-num">03</span><span class="block-name">{{ $t('relasim.sectionCurves') }}</span></div>
          <div class="curves-wrap">
            <div class="curve-legend">
              <button
                v-for="d in dims"
                :key="d.key"
                class="legend-chip"
                :class="{ active: activeDim === d.key }"
                :style="activeDim === d.key ? { background: d.color, color: '#fff', borderColor: d.color } : {}"
                @click="activeDim = d.key"
              >{{ $t('relasim.' + d.i18n) }}</button>
            </div>
            <svg class="curve-svg" :viewBox="`0 0 ${svgW} ${svgH}`" preserveAspectRatio="none">
              <!-- 网格 -->
              <line v-for="g in [0,25,50,75,100]" :key="g" :x1="padL" :x2="svgW - padR" :y1="yFor(g)" :y2="yFor(g)" class="grid-line" />
              <text v-for="g in [0,50,100]" :key="'t'+g" :x="padL - 8" :y="yFor(g) + 3" class="axis-label" text-anchor="end">{{ g }}</text>
              <!-- 曲线 -->
              <polyline
                v-for="(series, rel) in activeSeries"
                :key="rel"
                :points="pointsFor(series)"
                class="curve-line"
                :style="{ stroke: colorFor(rel) }"
              />
              <!-- 端点 -->
              <g v-for="(series, rel) in activeSeries" :key="'d'+rel">
                <circle
                  v-for="(v, idx) in series"
                  :key="idx"
                  :cx="xFor(idx)"
                  :cy="yFor(v)"
                  r="2.5"
                  :style="{ fill: colorFor(rel) }"
                  class="curve-dot"
                />
              </g>
            </svg>
            <div class="curve-rels">
              <span v-for="(series, rel) in activeSeries" :key="rel" class="rel-chip" :style="{ borderColor: colorFor(rel) }">
                <span class="rel-dot" :style="{ background: colorFor(rel) }"></span>{{ rel }}
              </span>
            </div>
            <p class="curve-hint">{{ $t('relasim.curveHint') }}</p>
          </div>
        </section>

        <!-- 关键转折点 -->
        <section class="block" v-if="data.report && data.report.turning_points && data.report.turning_points.length">
          <div class="block-meta"><span class="block-num">04</span><span class="block-name">{{ $t('relasim.sectionTurning') }}</span></div>
          <div class="turning-list">
            <div v-for="(tp, i) in data.report.turning_points" :key="i" class="turning-item">
              <span class="turning-mark">◆</span>
              <span class="turning-text">{{ tp }}</span>
            </div>
          </div>
        </section>

        <!-- 风险与建议 -->
        <div class="two-col">
          <section class="block" v-if="data.report && data.report.risks && data.report.risks.length">
            <div class="block-meta"><span class="block-num">05</span><span class="block-name">{{ $t('relasim.sectionRisks') }}</span></div>
            <ul class="list">
              <li v-for="(r, i) in data.report.risks" :key="i" class="list-item risk-item">{{ r }}</li>
            </ul>
          </section>
          <section class="block" v-if="data.report && data.report.suggestions && data.report.suggestions.length">
            <div class="block-meta"><span class="block-num">06</span><span class="block-name">{{ $t('relasim.sectionSuggestions') }}</span></div>
            <ul class="list">
              <li v-for="(s, i) in data.report.suggestions" :key="i" class="list-item sugg-item">{{ s }}</li>
            </ul>
          </section>
        </div>

        <!-- 总体分析 -->
        <section class="block" v-if="data.report && data.report.narrative">
          <div class="block-meta"><span class="block-num">07</span><span class="block-name">{{ $t('relasim.sectionNarrative') }}</span></div>
          <p class="narrative">{{ data.report.narrative }}</p>
        </section>

        <!-- 逐轮推演记录 -->
        <section class="block" v-if="data.simulation && data.simulation.rounds && data.simulation.rounds.length">
          <div class="block-meta"><span class="block-num">08</span><span class="block-name">{{ $t('relasim.sectionTimeline') }}</span></div>
          <div class="timeline">
            <div v-for="r in data.simulation.rounds" :key="r.round_index" class="round-card">
              <div class="round-head">
                <span class="round-label">{{ r.time_label }}</span>
                <span class="round-event" v-if="r.injected_event">⚡ {{ $t('relasim.eventBadge') }}</span>
              </div>
              <div v-if="r.injected_event" class="round-event-desc">{{ r.injected_event.description }}</div>
              <div v-for="(it, idx) in r.interactions" :key="idx" class="round-interaction">
                <span class="scenario-tag">{{ it.scenario }}</span>
                <p class="interaction-narrative">{{ it.narrative }}</p>
              </div>
              <p class="round-summary" v-if="r.summary">— {{ r.summary }}</p>
            </div>
          </div>
        </section>

        <!-- 免责声明 -->
        <p class="disclaimer" v-if="data.report && data.report.disclaimer">{{ data.report.disclaimer }}</p>

        <!-- 对话侧栏 -->
        <section class="block chat-block" v-if="data.graph && data.graph.persons">
          <div class="block-meta"><span class="block-num">09</span><span class="block-name">{{ $t('relasim.chatTitle') }}</span></div>
          <p class="chat-hint">{{ $t('relasim.chatHint') }}</p>
          <div class="chat-persons">
            <button
              v-for="p in data.graph.persons"
              :key="p.person_id"
              class="chat-person-btn"
              :class="{ active: chatPersonId === p.person_id }"
              @click="selectPerson(p.person_id)"
            >{{ p.name }}</button>
          </div>
          <div class="chat-window" ref="chatWindow">
            <div v-if="!chatMessages.length" class="chat-empty">{{ $t('relasim.chatEmpty') }}</div>
            <div v-for="(m, i) in chatMessages" :key="i" class="chat-msg" :class="m.role">
              <span class="msg-role">{{ m.role === 'user' ? 'YOU' : 'TA' }}</span>
              <span class="msg-text">{{ m.content }}</span>
            </div>
          </div>
          <div class="chat-input-row">
            <input
              v-model="chatInput"
              class="chat-input"
              :placeholder="$t('relasim.chatPlaceholder')"
              :disabled="chatSending"
              @keyup.enter="sendChat"
            />
            <button class="chat-send" @click="sendChat" :disabled="chatSending || !chatInput.trim()">
              {{ chatSending ? $t('relasim.chatThinking') : $t('relasim.chatSend') }} →
            </button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { getRelaSimStatus, getRelaSimResult, chatWithPerson } from '../api/relasim'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const phase = ref('loading') // loading | report | error
const progress = ref(0)
const statusMsg = ref('')
const errorMsg = ref('')
const data = ref(null)
const taskId = computed(() => route.params.taskId)

// 曲线
const dims = [
  { key: 'affection', i18n: 'dimAffection', color: '#FF4500' },
  { key: 'trust', i18n: 'dimTrust', color: '#3b82f6' },
  { key: 'dependence', i18n: 'dimDependence', color: '#9333ea' },
  { key: 'tension', i18n: 'dimTension', color: '#e11d48' },
  { key: 'commitment', i18n: 'dimCommitment', color: '#16a34a' }
]
const activeDim = ref('affection')
const svgW = 760
const svgH = 260
const padL = 36
const padR = 16
const padT = 16
const padB = 24

const relColors = ['#FF4500', '#3b82f6', '#9333ea', '#16a34a', '#eab308']
const colorMap = {}
function colorFor(rel) {
  if (!(rel in colorMap)) {
    colorMap[rel] = relColors[Object.keys(colorMap).length % relColors.length]
  }
  return colorMap[rel]
}

const curves = computed(() => (data.value && data.value.report && data.value.report.psychology_curves) || {})
const hasCurves = computed(() => Object.keys(curves.value).length > 0)
const activeSeries = computed(() => {
  const out = {}
  for (const [rel, series] of Object.entries(curves.value)) {
    const arr = series[activeDim.value]
    if (Array.isArray(arr) && arr.length) out[rel] = arr
  }
  return out
})

function xFor(idx) {
  const labels = (Object.values(curves.value)[0] || {}).labels || []
  const n = labels.length || 1
  const w = svgW - padL - padR
  return padL + (idx / Math.max(1, n - 1)) * w
}
function yFor(v) {
  const h = svgH - padT - padB
  return padT + (1 - (v || 0) / 100) * h
}
function pointsFor(series) {
  return series.map((v, idx) => `${xFor(idx)},${yFor(v)}`).join(' ')
}

const sortedOutcomes = computed(() => {
  const o = (data.value && data.value.report && data.value.report.outcomes) || []
  return [...o].sort((a, b) => b.probability - a.probability)
})

function attachLabel(style) {
  const map = {
    secure: t('relasim.attachmentSecure'),
    anxious: t('relasim.attachmentAnxious'),
    avoidant: t('relasim.attachmentAvoidant'),
    fearful: t('relasim.attachmentFearful')
  }
  return map[style] || style || '—'
}

// 对话
const chatPersonId = ref('')
const chatMessages = ref([])
const chatInput = ref('')
const chatSending = ref(false)
const chatWindow = ref(null)

function selectPerson(pid) {
  chatPersonId.value = pid
  chatMessages.value = []
}
async function sendChat() {
  if (!chatInput.value.trim() || chatSending.value || !chatPersonId.value) return
  const msg = chatInput.value.trim()
  chatMessages.value.push({ role: 'user', content: msg })
  chatInput.value = ''
  chatSending.value = true
  await nextTick(scrollChatBottom)
  try {
    const history = chatMessages.value
      .filter(m => m.role === 'assistant' || m.role === 'user')
      .slice(0, -1)
      .map(m => ({ role: m.role, content: m.content }))
    const res = await chatWithPerson({
      relasim_id: data.value.relasim_id,
      person_id: chatPersonId.value,
      message: msg,
      history
    })
    if (res && res.success && res.data) {
      chatMessages.value.push({ role: 'assistant', content: res.data.reply })
    } else {
      chatMessages.value.push({ role: 'assistant', content: '（无响应）' })
    }
  } catch (e) {
    chatMessages.value.push({ role: 'assistant', content: '（对话失败：' + (e.message || e) + '）' })
  } finally {
    chatSending.value = false
    await nextTick(scrollChatBottom)
  }
}
function scrollChatBottom() {
  if (chatWindow.value) chatWindow.value.scrollTop = chatWindow.value.scrollHeight
}

// 轮询
let pollTimer = null
async function poll() {
  try {
    const res = await getRelaSimStatus(taskId.value)
    if (!res || !res.success || !res.data) return
    const task = res.data
    progress.value = task.progress || 0
    statusMsg.value = task.message || ''
    if (task.status === 'completed' && task.result && task.result.relasim_id) {
      stopPoll()
      await loadResult(task.result.relasim_id)
    } else if (task.status === 'failed') {
      stopPoll()
      phase.value = 'error'
      errorMsg.value = task.error || 'unknown'
    }
  } catch (e) {
    console.error('poll error', e)
  }
}
async function loadResult(rid) {
  try {
    const res = await getRelaSimResult(rid)
    if (res && res.success && res.data) {
      data.value = res.data
      phase.value = 'report'
      if (data.value.graph && data.value.graph.persons && data.value.graph.persons[0]) {
        chatPersonId.value = data.value.graph.persons[0].person_id
      }
    } else {
      phase.value = 'error'
      errorMsg.value = (res && res.error) || 'load failed'
    }
  } catch (e) {
    phase.value = 'error'
    errorMsg.value = e.message || String(e)
  }
}
function startPoll() {
  poll()
  pollTimer = setInterval(poll, 2500)
}
function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function newRun() { router.push({ name: 'RelaSim' }) }
function goHome() { router.push('/') }

onMounted(() => {
  if (taskId.value) startPoll()
  else { phase.value = 'error'; errorMsg.value = 'no task id' }
})
onUnmounted(stopPoll)
</script>

<style scoped>
.relasim-report-page {
  min-height: 100vh;
  background: #FFFFFF;
  color: #000;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}
.navbar {
  height: 60px; background: #000; color: #fff;
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 40px; position: sticky; top: 0; z-index: 10;
}
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.1rem; cursor: pointer; }
.brand-suffix { color: #FF4500; font-weight: 500; }
.nav-links { display: flex; align-items: center; gap: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.nav-divider { color: #444; }
.nav-back { cursor: pointer; }
.nav-back:hover { color: #FF4500; }

.main-content { max-width: 980px; margin: 0 auto; padding: 60px 40px 120px; }

/* loading */
.loading-state { padding: 40px 0; }
.loading-tag { font-family: 'JetBrains Mono', monospace; color: #FF4500; font-size: 0.8rem; margin-bottom: 20px; }
.loading-title { font-family: 'JetBrains Mono', monospace; font-size: 3rem; font-weight: 600; letter-spacing: -1px; margin: 0 0 30px; }
.cursor { color: #FF4500; animation: blink 1s step-end infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.progress-track { width: 100%; height: 6px; background: #EEE; margin-bottom: 12px; }
.progress-fill { height: 100%; background: #FF4500; transition: width .4s ease; }
.progress-meta { display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #666; margin-bottom: 24px; }
.progress-pct { font-weight: 700; color: #000; }
.loading-hint { color: #999; font-size: 0.9rem; }

/* error */
.error-state { padding: 40px 0; }
.error-tag { font-family: 'JetBrains Mono', monospace; color: #e11d48; font-size: 0.8rem; margin-bottom: 16px; }
.error-title { font-size: 2rem; font-weight: 520; margin: 0 0 20px; }
.error-detail { background: #FAFAFA; border: 1px solid #EEE; padding: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #666; white-space: pre-wrap; max-height: 200px; overflow: auto; }
.retry-btn { margin-top: 24px; background: #000; color: #fff; border: none; padding: 14px 28px; font-family: 'JetBrains Mono', monospace; font-weight: 700; cursor: pointer; }
.retry-btn:hover { background: #FF4500; }

/* report */
.report-header { margin-bottom: 50px; }
.header-tag { font-family: 'JetBrains Mono', monospace; color: #FF4500; font-size: 0.8rem; margin-bottom: 14px; }
.report-title { font-size: 2.4rem; font-weight: 520; letter-spacing: -1px; margin: 0 0 16px; }
.report-context { color: #666; line-height: 1.7; font-size: 0.98rem; border-left: 2px solid #FF4500; padding-left: 14px; }

.block { margin-bottom: 56px; }
.block-meta { display: flex; align-items: baseline; gap: 12px; margin-bottom: 20px; }
.block-num { font-family: 'JetBrains Mono', monospace; font-weight: 800; color: #FF4500; font-size: 0.95rem; }
.block-name { font-size: 1.2rem; font-weight: 520; }

/* persons */
.persons-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.person-card { border: 1px solid #E5E5E5; padding: 20px; transition: all .2s; }
.person-card:hover { border-color: #FF4500; transform: translateY(-2px); }
.person-head { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.person-avatar { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #fff; font-size: 1.1rem; }
.person-avatar.female { background: #e11d48; }
.person-avatar.male { background: #3b82f6; }
.person-avatar.unknown { background: #666; }
.person-id { flex: 1; }
.person-name { font-weight: 600; font-size: 1.05rem; }
.person-sub { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #999; }
.attach-badge { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; padding: 3px 8px; border: 1px solid #DDD; color: #666; letter-spacing: 0.5px; }
.attach-badge.anxious { color: #e11d48; border-color: #fecdd3; background: #fff1f2; }
.attach-badge.avoidant { color: #3b82f6; border-color: #bfdbfe; background: #eff6ff; }
.attach-badge.fearful { color: #9333ea; border-color: #e9d5ff; background: #faf5ff; }
.attach-badge.secure { color: #16a34a; border-color: #bbf7d0; background: #f0fdf4; }
.person-fields { display: flex; flex-direction: column; gap: 10px; }
.pf { display: flex; flex-direction: column; gap: 2px; }
.pf-k { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; color: #999; letter-spacing: 0.5px; }
.pf-v { font-size: 0.85rem; color: #333; line-height: 1.5; }

/* outcomes */
.outcomes { display: flex; flex-direction: column; gap: 18px; }
.outcome-row { display: flex; gap: 16px; align-items: stretch; }
.outcome-bar-wrap { width: 8px; background: #F0F0F0; position: relative; }
.outcome-bar { position: absolute; bottom: 0; left: 0; width: 100%; background: #FF4500; transition: height .6s ease; }
.outcome-info { flex: 1; }
.outcome-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.outcome-label { font-weight: 600; font-size: 1.05rem; }
.outcome-pct { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.1rem; color: #FF4500; }
.outcome-rationale { color: #666; font-size: 0.88rem; line-height: 1.6; }

/* curves */
.curves-wrap { border: 1px solid #E5E5E5; padding: 24px; }
.curve-legend { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
.legend-chip { background: none; border: 1px solid #DDD; padding: 5px 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #666; cursor: pointer; transition: all .2s; }
.legend-chip:hover { border-color: #999; }
.curve-svg { width: 100%; height: 260px; display: block; }
.grid-line { stroke: #F0F0F0; stroke-width: 1; }
.axis-label { font-family: 'JetBrains Mono', monospace; font-size: 9px; fill: #BBB; }
.curve-line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.curve-dot { stroke: #fff; stroke-width: 1; }
.curve-rels { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
.rel-chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid; padding: 3px 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; }
.rel-dot { width: 8px; height: 8px; }
.curve-hint { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #999; margin-top: 12px; }

/* turning */
.turning-list { display: flex; flex-direction: column; gap: 14px; }
.turning-item { display: flex; gap: 12px; align-items: flex-start; }
.turning-mark { color: #FF4500; font-size: 0.9rem; line-height: 1.6; }
.turning-text { font-size: 0.95rem; line-height: 1.6; color: #333; }

/* two col */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
.list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.list-item { font-size: 0.9rem; line-height: 1.6; color: #444; padding-left: 18px; position: relative; }
.risk-item::before { content: '✕'; position: absolute; left: 0; color: #e11d48; font-weight: 700; }
.sugg-item::before { content: '→'; position: absolute; left: 0; color: #16a34a; font-weight: 700; }

/* narrative */
.narrative { font-size: 0.98rem; line-height: 1.85; color: #333; text-align: justify; }

/* timeline */
.timeline { display: flex; flex-direction: column; gap: 16px; }
.round-card { border: 1px solid #E5E5E5; padding: 18px 20px; }
.round-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.round-label { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.9rem; }
.round-event { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #FF4500; border: 1px solid #FF4500; padding: 2px 8px; }
.round-event-desc { font-size: 0.85rem; color: #FF4500; background: #fff5f1; padding: 8px 12px; margin-bottom: 10px; border-left: 2px solid #FF4500; }
.round-interaction { margin-bottom: 10px; }
.scenario-tag { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; color: #666; background: #F5F5F5; padding: 2px 8px; margin-bottom: 6px; }
.interaction-narrative { font-size: 0.88rem; line-height: 1.65; color: #444; margin: 0; }
.round-summary { font-size: 0.82rem; color: #999; font-style: italic; margin: 6px 0 0; }

.disclaimer { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #999; border-left: 2px solid #FF4500; padding-left: 12px; line-height: 1.6; margin: 40px 0; }

/* chat */
.chat-block { border: 1px solid #E5E5E5; padding: 24px; }
.chat-hint { font-size: 0.85rem; color: #999; margin: 0 0 16px; }
.chat-persons { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.chat-person-btn { background: none; border: 1px solid #DDD; padding: 6px 14px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #666; cursor: pointer; transition: all .2s; }
.chat-person-btn.active { background: #000; color: #fff; border-color: #000; }
.chat-window { height: 240px; overflow-y: auto; border: 1px solid #EEE; background: #FAFAFA; padding: 14px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 10px; }
.chat-empty { color: #BBB; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; text-align: center; margin-top: 80px; }
.chat-msg { display: flex; gap: 10px; align-items: flex-start; }
.msg-role { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; font-weight: 700; padding: 3px 6px; height: fit-content; letter-spacing: 0.5px; }
.chat-msg.user .msg-role { background: #000; color: #fff; }
.chat-msg.assistant .msg-role { background: #FF4500; color: #fff; }
.msg-text { font-size: 0.88rem; line-height: 1.6; color: #333; flex: 1; }
.chat-input-row { display: flex; gap: 10px; }
.chat-input { flex: 1; border: 1px solid #DDD; background: #FAFAFA; padding: 12px 14px; font-family: 'Noto Sans SC', system-ui, sans-serif; font-size: 0.9rem; outline: none; }
.chat-input:focus { border-color: #FF4500; background: #fff; }
.chat-send { background: #000; color: #fff; border: none; padding: 0 22px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.85rem; cursor: pointer; transition: all .2s; white-space: nowrap; }
.chat-send:hover:not(:disabled) { background: #FF4500; }
.chat-send:disabled { background: #E5E5E5; color: #999; cursor: not-allowed; }

@media (max-width: 768px) {
  .main-content { padding: 30px 20px 80px; }
  .two-col { grid-template-columns: 1fr; }
  .report-title { font-size: 1.8rem; }
}
</style>
