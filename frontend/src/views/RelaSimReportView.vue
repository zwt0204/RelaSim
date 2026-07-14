<template>
  <div class="relasim-report-page" :class="{ 'cockpit-mode': phase === 'loading' || phase === 'arrived' }">
    <div class="arrive-flash" v-if="flashing"></div>
    <nav class="navbar">
      <div class="nav-brand" @click="goHome">RELASIM<span class="brand-suffix">关系推演</span></div>
      <div class="nav-links">
        <LanguageSwitcher />
        <span class="nav-divider">|</span>
        <span class="nav-back" @click="newRun">{{ $t('relasim.backToInput') }} ↗</span>
      </div>
    </nav>

    <div class="main-content" :class="{ wide: phase === 'report' }">
      <!-- 时光舱：推演进行中 / 抵达（暗色驾驶舱） -->
      <div v-if="phase === 'loading' || phase === 'arrived'" class="cockpit">
        <!-- 时空穿梭星场（常态星流，穿梭时爆发光速线） -->
        <canvas ref="starCanvas" class="starfield"></canvas>
        <!-- 顶部：旅程轨道 -->
        <div class="voyage-head">
          <span class="voyage-meta">{{ Math.round(displayProgress) }}% · {{ $t('relasim.loadingElapsed') }} {{ elapsed }}</span>
        </div>
        <div class="voyage-rail">
          <template v-for="(tk, i) in railTicks" :key="tk.idx">
            <div
              class="rail-node"
              :class="{
                done: tk.kind === 'time' && tk.ready && tk.idx !== timeIndex,
                cur: tk.kind === 'time' && tk.idx === timeIndex,
                off: !tk.ready,
                dest: tk.kind === 'dest',
                blink: tk.kind === 'dest' && currentStage === 'report' && phase === 'loading',
                lit: tk.kind === 'dest' && phase === 'arrived'
              }"
              @click="tk.kind === 'time' && tk.ready && onScrub(tk.idx)"
            >
              <i class="rail-dot">{{ tk.kind === 'dest' ? '◇' : '' }}</i>
              <em class="rail-label">{{ tk.label }}</em>
            </div>
            <div v-if="i < railTicks.length - 1" class="rail-line" :class="{ lit: railTicks[i + 1].ready }"></div>
          </template>
        </div>

        <!-- 中央：校准 / 巨大时间标签 + 图谱主角 -->
        <div class="cockpit-center">
          <div v-if="!hasGraph" class="calibrating">
            <h1 class="calib-title">CALIBRATING<span class="cursor">_</span></h1>
            <div class="calib-scan"><span></span></div>
            <p class="calib-sub">{{ statusMsg || $t('relasim.calibrating') }}</p>
          </div>
          <template v-else>
            <div class="big-time-wrap" v-if="revealDone">
              <span class="big-time" :key="timeIndex">{{ tickLabel(timeIndex) }}</span>
            </div>
            <RelaSimGraph
              dark
              class="cockpit-graph"
              :class="{ warping: !!warpFx }"
              :nodes="graphNodes"
              :edges="graphEdges"
              :ticks="timeTicks"
              :time-index="timeIndex"
              :max-index="latestRoundIndex"
              :following="followLatest"
              :warp="warpFx"
              :visible-nodes="revealNodes"
              :ghost-nodes="revealGhost"
              :visible-edges="revealEdges"
              @scrub="onScrub"
              @now="jumpNow"
            />
          </template>
        </div>

        <!-- 抵达面板：定格 + 结局预告 + 进报告 -->
        <div v-if="phase === 'arrived'" class="arrive-panel">
          <div class="arrive-tag">✔ {{ $t('relasim.arrived') }} · {{ tickLabel(latestRoundIndex) }}</div>
          <div class="arrive-outcome" v-if="topOutcome">
            <span class="ao-tag">◆ {{ $t('relasim.mostLikely') }}</span>
            <span class="ao-label">{{ topOutcome.label }}</span>
            <span class="ao-pct">{{ Math.round(topOutcome.probability * 100) }}%</span>
          </div>
          <button class="arrive-btn" @click="goReport">{{ $t('relasim.viewFullReport') }} →</button>
        </div>

        <!-- 底部：终端（建档日志 → 逐轮小结 → 报告生成，column-reverse 最新钉底） -->
        <div class="cockpit-term" v-if="phase === 'loading'">
          <span class="term-prompt">> {{ $t('relasim.terminalPrompt') }}</span>
          <div class="term-history">
            <div v-if="currentStage === 'report'" class="term-line">
              <span class="term-text">{{ $t('relasim.reportBuilding') }}<span class="term-caret">▋</span></span>
            </div>
            <div v-else-if="simBusyLine" class="term-line busy">
              <span class="term-text">{{ simBusyLine }}<span class="term-caret">▋</span></span>
            </div>
            <div v-for="(h, i) in terminalHistory" :key="'r' + h.idx" class="term-line">
              <span class="term-time" v-if="h.time_label">{{ h.time_label }}  </span>
              <span class="term-text">{{ i === 0 ? typedText : h.summary }}<span class="term-caret" v-if="i === 0 && currentStage === 'simulating' && !simBusyLine">▋</span></span>
            </div>
            <div v-for="(l, i) in calibLogReversed" :key="'c' + (calibLogReversed.length - i)" class="term-line" :class="l.cls">
              <span class="term-text">{{ l.text }}<span class="term-caret" v-if="i === 0 && !revealDone && !terminalHistory.length">▋</span></span>
            </div>
            <div v-if="!terminalHistory.length && !calibLog.length && currentStage !== 'report'" class="term-line">
              <span class="term-text">{{ statusMsg || $t('relasim.loadingHint') }}<span class="term-caret">▋</span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误态 -->
      <div v-else-if="phase === 'error'" class="error-state">
        <div class="error-tag">✕ ERROR</div>
        <h1 class="error-title">{{ $t('relasim.errorRun') }}</h1>
        <pre class="error-detail">{{ errorMsg }}</pre>
        <button class="retry-btn" @click="newRun">{{ $t('relasim.backToInput') }} →</button>
      </div>

      <!-- 报告态 -->
      <div v-else-if="phase === 'report' && data" class="report-body report-reveal">
        <!-- 结论横幅：一眼看到答案 -->
        <div class="verdict-banner" v-if="topOutcome">
          <span class="verdict-tag">◆ {{ $t('relasim.mostLikely') }}</span>
          <span class="verdict-label">{{ topOutcome.label }}</span>
          <span class="verdict-pct">{{ Math.round(topOutcome.probability * 100) }}%</span>
          <span class="verdict-lead" v-if="narrativeLead">{{ narrativeLead }}</span>
        </div>

        <div class="report-cols">
          <div class="report-main">
        <!-- 标题 -->
        <header class="report-header">
          <div class="header-tag">◇ {{ $t('relasim.reportTitle') }}</div>
          <h1 class="report-title">{{ $t('relasim.reportTitle') }}</h1>
          <p class="report-context" v-if="data.graph && data.graph.context">{{ data.graph.context }}</p>
        </header>

        <!-- 参与的人 -->
        <section class="block" v-if="data.graph && data.graph.persons">
          <div class="block-meta"><span class="block-num">01</span><span class="block-name">{{ $t('relasim.sectionPersons') }}</span></div>
          <!-- 关系图谱（回看：与推演过程相同的可视化 + 时间穿梭滑块） -->
          <RelaSimGraph
            v-if="hasGraph"
            class="report-graph"
            :nodes="graphNodes"
            :edges="graphEdges"
            :ticks="timeTicks"
            :time-index="timeIndex"
            :max-index="latestRoundIndex"
            :following="followLatest"
            :warp="warpFx"
            @scrub="onScrub"
            @now="jumpNow"
          />
          <!-- 人物卡：紧凑一行，点击展开详情 -->
          <div class="persons-list">
            <div v-for="p in data.graph.persons" :key="p.person_id" class="person-row" @click="toggle('person' + p.person_id)">
              <div class="person-head">
                <span class="person-avatar" :class="p.gender">{{ (p.name || '?').slice(0,1) }}</span>
                <div class="person-id">
                  <div class="person-name">{{ p.name }}</div>
                  <div class="person-sub">{{ p.gender === 'female' ? '♀' : p.gender === 'male' ? '♂' : '·' }} {{ p.age || '—' }}</div>
                </div>
                <span class="attach-badge" :class="p.attachment_style">{{ attachLabel(p.attachment_style) }}</span>
                <span class="person-expand">{{ expanded['person' + p.person_id] ? '−' : '+' }}</span>
              </div>
              <div class="person-fields" v-if="expanded['person' + p.person_id]">
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
                <p
                  class="outcome-rationale clamp-toggle"
                  :class="{ 'clamp-2': !expanded['outcome' + i] }"
                  v-if="o.rationale"
                  @click="toggle('outcome' + i)"
                >{{ o.rationale }}</p>
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
          <section class="block" v-if="allRisks.length">
            <div class="block-meta"><span class="block-num">05</span><span class="block-name">{{ $t('relasim.sectionRisks') }}</span></div>
            <ul class="list">
              <li
                v-for="(r, i) in visibleRisks"
                :key="i"
                class="list-item risk-item clamp-toggle"
                :class="{ 'clamp-2': !expanded['risk' + i] }"
                @click="toggle('risk' + i)"
              >{{ r }}</li>
            </ul>
            <button v-if="allRisks.length > LIST_LIMIT" class="expand-btn" @click="toggle('risks')">
              {{ expanded.risks ? $t('relasim.collapse') + ' ↑' : $t('relasim.showMoreN', { n: allRisks.length - LIST_LIMIT }) + ' ↓' }}
            </button>
          </section>
          <section class="block" v-if="allSuggestions.length">
            <div class="block-meta"><span class="block-num">06</span><span class="block-name">{{ $t('relasim.sectionSuggestions') }}</span></div>
            <ul class="list">
              <li
                v-for="(s, i) in visibleSuggestions"
                :key="i"
                class="list-item sugg-item clamp-toggle"
                :class="{ 'clamp-2': !expanded['sugg' + i] }"
                @click="toggle('sugg' + i)"
              >{{ s }}</li>
            </ul>
            <button v-if="allSuggestions.length > LIST_LIMIT" class="expand-btn" @click="toggle('suggestions')">
              {{ expanded.suggestions ? $t('relasim.collapse') + ' ↑' : $t('relasim.showMoreN', { n: allSuggestions.length - LIST_LIMIT }) + ' ↓' }}
            </button>
          </section>
        </div>

        <!-- 总体分析 -->
        <section class="block" v-if="data.report && data.report.narrative">
          <div class="block-meta"><span class="block-num">07</span><span class="block-name">{{ $t('relasim.sectionNarrative') }}</span></div>
          <p class="narrative" :class="{ 'clamp-3': !expanded.narrative }">{{ data.report.narrative }}</p>
          <button v-if="data.report.narrative.length > 120" class="expand-btn" @click="toggle('narrative')">
            {{ expanded.narrative ? $t('relasim.collapse') + ' ↑' : $t('relasim.expand') + ' ↓' }}
          </button>
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
              <!-- 默认只显示本轮小结 + 场景标签，长篇互动叙事折叠 -->
              <p class="round-summary" v-if="r.summary">{{ r.summary }}</p>
              <div class="round-tags" v-if="!expanded['round' + r.round_index] && r.interactions && r.interactions.length">
                <span v-for="(it, idx) in r.interactions" :key="idx" class="scenario-tag">{{ it.scenario }}</span>
              </div>
              <div v-if="expanded['round' + r.round_index]" class="round-detail">
                <div v-for="(it, idx) in r.interactions" :key="idx" class="round-interaction">
                  <span class="scenario-tag">{{ it.scenario }}</span>
                  <p class="interaction-narrative">{{ it.narrative }}</p>
                </div>
              </div>
              <button v-if="r.interactions && r.interactions.length" class="expand-btn" @click="toggle('round' + r.round_index)">
                {{ expanded['round' + r.round_index] ? $t('relasim.collapseRound') + ' ↑' : $t('relasim.expandRound') + ' ↓' }}
              </button>
            </div>
          </div>
        </section>

        <!-- 免责声明 -->
        <p class="disclaimer" v-if="data.report && data.report.disclaimer">{{ data.report.disclaimer }}</p>
          </div><!-- /report-main -->

          <!-- 右列：与当事人对话（sticky 常驻） -->
          <aside class="chat-column" v-if="data.graph && data.graph.persons">
            <div class="chat-dock">
              <div class="chat-dock-head">
                <span class="chat-dock-tag">◇ {{ $t('relasim.chatDock') }}</span>
              </div>
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
            </div>
          </aside>
        </div><!-- /report-cols -->
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import RelaSimGraph from '../components/RelaSimGraph.vue'
import { getRelaSimStatus, getRelaSimResult, chatWithPerson } from '../api/relasim'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const phase = ref('loading') // loading | arrived | report | error
const progress = ref(0)
const statusMsg = ref('')
const errorMsg = ref('')
const data = ref(null)
const taskId = computed(() => route.params.taskId)

// ===== 推演流程可视化状态 =====
// total_rounds 在首 poll 中从 task.metadata.rounds 取得
const totalRounds = ref(0)
// 后端结构化阶段数据 { stage, round_index, total_rounds, time_label, summary }
const taskProgressDetail = ref(null)
// 缓存每轮已完成小结，应对轮询覆盖、轮进行中无信号
const completedSummaries = ref([])
// 终端历史：全部已完成轮小结（倒序渲染 + CSS column-reverse 自动钉底）
const terminalHistory = computed(() =>
  completedSummaries.value
    .map((s, i) => (s && s.summary ? { ...s, idx: i } : null))
    .filter(Boolean)
    .reverse()
)

// ===== 关系图谱（build_graph 完成后由 progress_detail.graph 透出，收到即冻结可回看）=====
const relationGraph = ref(null)
const hasGraph = computed(() => !!(relationGraph.value && relationGraph.value.persons && relationGraph.value.persons.length))
const gSvgW = 760
const gSvgH = 340
const G_NODE_R = 30
// 节点定位：N<=2 横排；3~6 环形；>6 网格
const graphNodes = computed(() => {
  const persons = (relationGraph.value && relationGraph.value.persons) || []
  const n = persons.length
  const cx = gSvgW / 2
  const cy = gSvgH / 2
  return persons.map((p, i) => {
    let x, y
    if (n <= 2) {
      x = n === 1 ? cx : cx + (i === 0 ? -1 : 1) * 200
      y = cy
    } else if (n <= 6) {
      const ang = (i / n) * Math.PI * 2 - Math.PI / 2
      x = cx + Math.cos(ang) * (cx - 120)
      y = cy + Math.sin(ang) * (cy - 70)
    } else {
      const cols = Math.ceil(Math.sqrt(n))
      const rows = Math.ceil(n / cols)
      const col = i % cols
      const row = Math.floor(i / cols)
      x = 90 + (col / Math.max(1, cols - 1)) * (gSvgW - 180)
      y = 60 + (row / Math.max(1, rows - 1)) * (gSvgH - 120)
    }
    return { ...p, x, y }
  })
})
const graphNodeMap = computed(() => {
  const m = {}
  for (const nd of graphNodes.value) m[nd.person_id] = nd
  return m
})
// ===== 时间穿梭：每轮情感快照 + 时刻指针 =====
// roundSnapshots[i] = 第 i 轮结束时 { "p_a->p_b": {affection,...5维} }
const roundSnapshots = ref([])
// -1 = 初始时刻（graph.edges.feeling）；i = 第 i 轮结束后
const timeIndex = ref(-1)
// 仿真进行中自动跟随最新完成轮；用户拖滑块回看即暂停跟随
const followLatest = ref(true)
const latestRoundIndex = computed(() => {
  const arr = roundSnapshots.value
  for (let i = arr.length - 1; i >= 0; i--) if (arr[i]) return i
  return -1
})
// 指定时刻某条有向关系的情感值：从 timeIndex 往前找最近的快照，缺省回退初始
function feelingAt(key, initial) {
  for (let i = timeIndex.value; i >= 0; i--) {
    const snap = roundSnapshots.value[i]
    if (snap && snap[key]) return snap[key]
  }
  return initial || {}
}
// 边配色三档：高张力红 / 暖关系橙 / 平淡灰
function edgeColor(f) {
  if ((f.tension || 0) >= 60) return '#e11d48'
  const warm = ((f.affection || 0) + (f.trust || 0) + (f.commitment || 0)) / 3
  if (warm >= 55) return '#FF4500'
  return '#999'
}
// 时间轴刻度：初始 + 每轮 time_label
const timeTicks = computed(() => {
  const ticks = [{ idx: -1, label: t('relasim.timeInitial'), ready: true }]
  const n = totalRounds.value || 0
  for (let i = 0; i < n; i++) {
    const s = completedSummaries.value[i]
    ticks.push({ idx: i, label: (s && s.time_label) || `#${i + 1}`, ready: !!roundSnapshots.value[i] })
  }
  return ticks
})
function tickLabel(i) {
  if (i < 0) return t('relasim.timeInitial')
  const s = completedSummaries.value[i]
  return (s && s.time_label) || `#${i + 1}`
}
// 穿梭到时刻 i：翻转标签 + 扫光过场（:key 变化重放动画）
const warpFx = ref(null)
let warpTimer = null
function travelTo(i, withFx = true) {
  i = Math.max(-1, Math.min(latestRoundIndex.value, i))
  if (i === timeIndex.value) return
  if (withFx) {
    warpFx.value = { from: tickLabel(timeIndex.value), to: tickLabel(i), key: `${timeIndex.value}>${i}` }
    if (warpTimer) clearTimeout(warpTimer)
    warpTimer = setTimeout(() => { warpFx.value = null }, 750)
    boostWarp() // 星场爆发成光速线
  }
  timeIndex.value = i
}
function onScrub(v) {
  followLatest.value = v >= latestRoundIndex.value
  travelTo(v)
}
function jumpNow() {
  followLatest.value = true
  travelTo(latestRoundIndex.value)
}

// ===== 时光舱：旅程轨道 / 打字机 / 抵达流转 =====
// 轨道刻度 = 时间刻度 + 终点(报告)
const railTicks = computed(() => ([
  ...timeTicks.value.map(tk => ({ ...tk, kind: 'time' })),
  { idx: 'dest', kind: 'dest', label: t('relasim.destReport'), ready: phase.value === 'arrived' }
]))
// 打字机：最新完成轮小结逐字打出
const typedText = ref('')
let typeTimer = null
watch(() => (terminalHistory.value[0] ? terminalHistory.value[0].idx : -1), () => {
  const item = terminalHistory.value[0]
  if (typeTimer) { clearInterval(typeTimer); typeTimer = null }
  if (!item) { typedText.value = ''; return }
  const full = item.summary || ''
  typedText.value = ''
  let i = 0
  typeTimer = setInterval(() => {
    i += 2
    typedText.value = full.slice(0, i)
    if (i >= full.length) { clearInterval(typeTimer); typeTimer = null }
  }, 30)
})
// 抵达 → 白光过场 → 报告
const flashing = ref(false)
function goReport() {
  flashing.value = true
  setTimeout(() => {
    phase.value = 'report'
    flashing.value = false
    window.scrollTo({ top: 0 })
  }, 380)
}

// ===== 时空穿梭星场（canvas）：常态缓慢星流，穿梭时爆发成光速拉线 =====
const starCanvas = ref(null)
let starRaf = null
let stars = []
let warpPower = 0    // 当前爆发强度（0~1，缓动逼近 warpTarget）
let warpTarget = 0
let warpBoostTimer = null
let starFit = null
function boostWarp(ms = 950) {
  warpTarget = 1
  if (warpBoostTimer) clearTimeout(warpBoostTimer)
  warpBoostTimer = setTimeout(() => { warpTarget = 0 }, ms)
}
function resetStar(s, w, h) {
  s.x = (Math.random() - 0.5) * w
  s.y = (Math.random() - 0.5) * h
  s.z = Math.random() * 0.9 + 0.1
}
function startStarfield() {
  const cv = starCanvas.value
  if (!cv || starRaf) return
  const ctx = cv.getContext('2d')
  starFit = () => { cv.width = window.innerWidth; cv.height = window.innerHeight }
  starFit()
  window.addEventListener('resize', starFit)
  stars = Array.from({ length: 240 }, () => { const s = {}; resetStar(s, cv.width, cv.height); return s })
  ctx.fillStyle = '#0A0A0A'
  ctx.fillRect(0, 0, cv.width, cv.height)
  const step = () => {
    warpPower += (warpTarget - warpPower) * 0.07
    const w = cv.width
    const h = cv.height
    const cx = w / 2
    const cy = h * 0.42
    // 半透明覆盖产生运动拖影；爆发时拖影更长
    ctx.fillStyle = `rgba(10,10,10,${0.5 - warpPower * 0.3})`
    ctx.fillRect(0, 0, w, h)
    for (const s of stars) {
      const pz = s.z
      s.z -= 0.0016 * (1 + warpPower * 30)
      if (s.z <= 0.03) { resetStar(s, w, h); s.z = 1; continue }
      const sx = cx + s.x / s.z
      const sy = cy + s.y / s.z
      if (sx < -20 || sx > w + 20 || sy < -20 || sy > h + 20) { resetStar(s, w, h); s.z = 1; continue }
      const px = cx + s.x / pz
      const py = cy + s.y / pz
      ctx.strokeStyle = warpPower > 0.12
        ? `rgba(255,${140 - Math.round(warpPower * 60)},60,${Math.min(1, 0.3 + warpPower * 0.8)})`
        : 'rgba(190,190,205,0.65)'
      ctx.lineWidth = Math.max(0.4, 1.7 * (1 - s.z))
      ctx.beginPath()
      ctx.moveTo(px, py)
      ctx.lineTo(sx, sy)
      ctx.stroke()
    }
    starRaf = requestAnimationFrame(step)
  }
  starRaf = requestAnimationFrame(step)
}
function stopStarfield() {
  if (starRaf) { cancelAnimationFrame(starRaf); starRaf = null }
  if (starFit) { window.removeEventListener('resize', starFit); starFit = null }
}
// 舱内时启动星场；离开（进报告/出错）时停止
watch(phase, p => {
  if (p === 'loading' || p === 'arrived') nextTick(startStarfield)
  else stopStarfield()
})

// ===== 图谱建档揭晓：分镜头编排（数据已到手，揭晓有节奏）=====
// -1 = 未启用门控（全部显示）
const revealNodes = ref(-1)
const revealGhost = ref(-1)
const revealEdges = ref(-1)
const revealDone = ref(true)
const calibLog = ref([]) // { text, cls } 建档终端日志
let revealTimers = []
function rlog(text, cls = '') { calibLog.value.push({ text, cls }) }
function rt(fn, delay) { revealTimers.push(setTimeout(fn, delay)) }
const calibLogReversed = computed(() => [...calibLog.value].reverse())
function runReveal() {
  const g = relationGraph.value
  if (!g) return
  const persons = g.persons || []
  const edges = g.edges || []
  // 中途刷新已有轮次数据 / 非推演中：跳过编排直接全量显示
  if (latestRoundIndex.value >= 0 || phase.value !== 'loading') {
    revealNodes.value = -1; revealGhost.value = -1; revealEdges.value = -1
    revealDone.value = true
    return
  }
  revealNodes.value = 0; revealGhost.value = 0; revealEdges.value = 0
  revealDone.value = false
  calibLog.value = []
  let d = 200
  rt(() => rlog(t('relasim.calibParse')), d); d += 550
  // 逐句"扫描"关系背景摘要（分析的是用户自己的材料）
  const ctx = (g.context || '').split('。').map(s => s.trim()).filter(Boolean).slice(0, 3)
  ctx.forEach(s => { rt(() => rlog('· ' + s + '。', 'scan'), d); d += 450 })
  // 逐人建档：候选幽灵 → 画像确认
  persons.forEach((p, i) => {
    rt(() => {
      revealGhost.value = i + 1
      rlog(t('relasim.calibPerson', { i: i + 1, name: p.name || '?' }))
    }, d); d += 900
    rt(() => {
      revealNodes.value = i + 1
      rlog(t('relasim.calibProfile', {
        attach: attachLabel(p.attachment_style),
        trait: (p.personality || '').split(/[，,。]/)[0] || '—'
      }))
    }, d); d += 900
  })
  // 逐条推断关系
  edges.forEach((e, j) => {
    const sn = (persons.find(x => x.person_id === e.source_id) || {}).name || '?'
    const tn = (persons.find(x => x.person_id === e.target_id) || {}).name || '?'
    rt(() => {
      revealEdges.value = j + 1
      rlog(t('relasim.calibRelation', { a: sn, b: tn, label: e.label || '' }))
    }, d); d += 1000
  })
  rt(() => {
    revealDone.value = true
    rlog(t('relasim.calibDone', { n: persons.length, m: edges.length }), 'ok')
    boostWarp(1100)
  }, d)
}
// 图谱首次亮起 → 启动建档编排
watch(hasGraph, v => { if (v) runReveal() })

// ===== 仿真"进行中"状态行：等待下一轮时轮播场景提示 =====
const SCENARIO_HINTS = ['日常互动', '约会相处', '深度对话', '冲突摩擦', '外部压力']
const busyHintIdx = ref(0)
let busyTimer = null
const simBusyLine = computed(() => {
  if (currentStage.value !== 'simulating' || !revealDone.value) return ''
  if (latestRoundIndex.value + 1 >= (totalRounds.value || 0)) return ''
  const n = latestRoundIndex.value + 2
  return t('relasim.simRoundBusy', { n }) + ' · ' + SCENARIO_HINTS[busyHintIdx.value] + '…'
})

// 图谱 hover 检视 / 依恋环配色内聚在 RelaSimGraph 组件中

// 有向边：双向对(A→B / B→A)向两侧弯曲避免重叠；粗细/颜色按 timeIndex 时刻的情感值
const graphEdges = computed(() => {
  const edges = (relationGraph.value && relationGraph.value.edges) || []
  const map = graphNodeMap.value
  const out = []
  edges.forEach((e, i) => {
    const s = map[e.source_id]
    const t2 = map[e.target_id]
    if (!s || !t2) return
    const dx = t2.x - s.x
    const dy = t2.y - s.y
    const len = Math.hypot(dx, dy) || 1
    const ux = dx / len
    const uy = dy / len
    const x1 = s.x + ux * G_NODE_R
    const y1 = s.y + uy * G_NODE_R
    const x2 = t2.x - ux * (G_NODE_R + 8) // 留出箭头
    const y2 = t2.y - uy * (G_NODE_R + 8)
    // 双向成对时按 id 序各弯一侧；孤边微弯
    const side = e.source_id < e.target_id ? 1 : -1
    const off = side * Math.min(26, len * 0.12)
    const px = -uy
    const py = ux
    const mx = (x1 + x2) / 2 + px * off
    const my = (y1 + y2) / 2 + py * off
    const feelKey = `${e.source_id}->${e.target_id}`
    const f = feelingAt(feelKey, e.feeling)
    const strength = Math.max(0, Math.min(1, ((f.affection || 0) + (f.commitment || 0)) / 200))
    out.push({
      key: `${feelKey}-${i}`,
      d: `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`,
      label: e.label || '',
      lx: (x1 + x2) / 2 + px * off * 1.35,
      ly: (y1 + y2) / 2 + py * off * 1.35 + (side > 0 ? -4 : 10),
      width: 1.5 + strength * 4.5,
      color: edgeColor(f),
      feeling: f,
      sourceName: s.name,
      targetName: t2.name,
      delay: i * 260 + 400 // 节点先弹入，边随后逐条画出
    })
  })
  return out
})

// ===== 报告折叠态（narrative / 每轮详情 / outcome rationale / risks / suggestions）=====
const expanded = reactive({})
function toggle(key) { expanded[key] = !expanded[key] }
const LIST_LIMIT = 3
const allRisks = computed(() => (data.value && data.value.report && data.value.report.risks) || [])
const allSuggestions = computed(() => (data.value && data.value.report && data.value.report.suggestions) || [])
const visibleRisks = computed(() => (expanded.risks ? allRisks.value : allRisks.value.slice(0, LIST_LIMIT)))
const visibleSuggestions = computed(() => (expanded.suggestions ? allSuggestions.value : allSuggestions.value.slice(0, LIST_LIMIT)))
// 已用时长 mm:ss
const elapsedSec = ref(0)
const elapsed = computed(() => {
  const m = String(Math.floor(elapsedSec.value / 60)).padStart(2, '0')
  const s = String(elapsedSec.value % 60).padStart(2, '0')
  return `${m}:${s}`
})
// 大号进度数字：rAF 补间到 progress，丝滑递增
const displayProgress = ref(0)
let rafId = null
function tweenProgress() {
  if (rafId) cancelAnimationFrame(rafId)
  const step = () => {
    const diff = progress.value - displayProgress.value
    if (Math.abs(diff) < 0.4) {
      displayProgress.value = progress.value
      rafId = null
      return
    }
    displayProgress.value += diff * 0.15
    rafId = requestAnimationFrame(step)
  }
  rafId = requestAnimationFrame(step)
}
let elapsedTimer = null

// 阶段机：progress <10 graph | <90 simulating | <100 report | >=100 done
const currentStage = computed(() => {
  const p = progress.value
  if (p < 10) return 'graph'
  if (p < 90) return 'simulating'
  if (p < 100) return 'report'
  return 'done'
})
// 已完成轮数（parseMessage 回退路径使用）
const completedRounds = computed(() => {
  const p = progress.value
  const N = totalRounds.value || 0
  if (p < 10) return 0
  if (p >= 90) return N
  const byProg = Math.floor((p - 10) / 75 * N)
  // completedSummaries 更可信（来自每轮完成回调）
  const byCache = completedSummaries.value.filter(Boolean).length
  return Math.max(0, Math.min(N, Math.max(byProg, byCache)))
})

// 解析中文 message「推演中：第 1 周 — 小结」作 progress_detail 缺席回退
function parseMessage(msg) {
  if (!msg) return null
  let m = msg.match(/^推演中：(.+?)\s*—\s*(.{0,60})/)
  if (!m) m = msg.match(/^Simulating[:：]\s*(.+?)\s*—\s*(.{0,60})/)
  if (!m) return null
  return { time_label: m[1].trim(), summary: m[2].trim() }
}

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
// 结论横幅：最高概率结局 + 总评首句
const topOutcome = computed(() => sortedOutcomes.value[0] || null)
const narrativeLead = computed(() => {
  const n = (data.value && data.value.report && data.value.report.narrative) || ''
  const first = n.split('。')[0]
  return first ? first + (n.includes('。') ? '。' : '') : ''
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
    if (task.metadata && task.metadata.rounds) totalRounds.value = task.metadata.rounds
    if (task.progress_detail) taskProgressDetail.value = task.progress_detail

    // 关系图谱：build_graph 完成后每次进度更新都随带，收到即冻结（回看产物）
    const pdg = task.progress_detail && task.progress_detail.graph
    if (pdg && pdg.persons && pdg.persons.length && !relationGraph.value) {
      relationGraph.value = pdg
    }

    // 缓存每轮已完成小结（优先 progress_detail，回退 message 正则）
    const pd = task.progress_detail
    if (pd && pd.stage === 'simulating' && pd.round_index != null) {
      const idx = pd.round_index
      completedSummaries.value[idx] = { time_label: pd.time_label, summary: pd.summary || '' }
      if (pd.snapshot) roundSnapshots.value[idx] = pd.snapshot
    } else if (statusMsg.value) {
      const parsed = parseMessage(statusMsg.value)
      if (parsed) {
        const c = completedRounds.value
        if (c > 0 && !completedSummaries.value[c - 1]) {
          completedSummaries.value[c - 1] = parsed
        }
      }
    }

    tweenProgress()

    // 时间穿梭：跟随最新完成轮（新快照到达时带过场特效前进）
    if (followLatest.value && latestRoundIndex.value > timeIndex.value) {
      travelTo(latestRoundIndex.value)
    }

    if (task.status === 'completed' && task.result && task.result.relasim_id) {
      stopPoll()
      progress.value = 100
      tweenProgress()
      // 先把结果加载好（抵达页要展示最可能结局预告），成功后 phase='arrived'
      loadResult(task.result.relasim_id)
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
      // 停在「抵达」画面（最终图谱定格 + 结局预告），用户点击后进报告
      phase.value = 'arrived'
      // 报告态也保留图谱可视化（回看第一步产物）；若推演中未捕获则从结果补
      if (!relationGraph.value && data.value.graph && data.value.graph.persons) {
        relationGraph.value = data.value.graph
      }
      // 时间穿梭数据补全：每轮快照与时间标签来自最终结果，默认停在最终时刻
      if (data.value.simulation && Array.isArray(data.value.simulation.rounds)) {
        const rounds = data.value.simulation.rounds
        if (!totalRounds.value) totalRounds.value = rounds.length
        rounds.forEach((r, i) => {
          if (r.snapshot) roundSnapshots.value[i] = r.snapshot
          if (!completedSummaries.value[i]) {
            completedSummaries.value[i] = { time_label: r.time_label, summary: r.summary || '' }
          }
        })
        timeIndex.value = latestRoundIndex.value
      }
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
  elapsedTimer = setInterval(() => { elapsedSec.value++ }, 1000)
}
function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function newRun() { router.push({ name: 'RelaSim' }) }
function goHome() { router.push('/') }

onMounted(() => {
  if (taskId.value) startPoll()
  else { phase.value = 'error'; errorMsg.value = 'no task id' }
  nextTick(startStarfield)
  busyTimer = setInterval(() => { busyHintIdx.value = (busyHintIdx.value + 1) % SCENARIO_HINTS.length }, 2200)
})
onUnmounted(() => {
  stopPoll()
  stopStarfield()
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
  if (rafId) { cancelAnimationFrame(rafId); rafId = null }
  if (warpTimer) { clearTimeout(warpTimer); warpTimer = null }
  if (typeTimer) { clearInterval(typeTimer); typeTimer = null }
  if (warpBoostTimer) { clearTimeout(warpBoostTimer); warpBoostTimer = null }
  if (busyTimer) { clearInterval(busyTimer); busyTimer = null }
  revealTimers.forEach(clearTimeout)
  revealTimers = []
})
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
/* 报告态放宽以容纳右列对话 */
.main-content.wide { max-width: 1320px; }

/* 结论横幅 */
.verdict-banner { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; background: #000; color: #fff; padding: 18px 24px; margin-bottom: 36px; font-family: 'JetBrains Mono', monospace; }
.verdict-tag { color: #FF4500; font-size: 0.72rem; letter-spacing: 0.5px; }
.verdict-label { font-size: 1.25rem; font-weight: 800; }
.verdict-pct { font-size: 1.25rem; font-weight: 800; color: #FF4500; }
.verdict-lead { flex-basis: 100%; color: #BBB; font-size: 0.78rem; line-height: 1.6; font-family: 'Noto Sans SC', system-ui, sans-serif; }

/* 双栏：左正文 + 右对话（sticky 常驻） */
.report-cols { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 36px; align-items: start; }
.report-main { min-width: 0; }
.chat-column { position: sticky; top: 76px; }
.chat-dock { border: 1px solid #E5E5E5; padding: 18px; display: flex; flex-direction: column; max-height: calc(100vh - 110px); }
.chat-dock-head { margin-bottom: 10px; }
.chat-dock-tag { font-family: 'JetBrains Mono', monospace; color: #FF4500; font-size: 0.75rem; letter-spacing: 0.5px; }
.chat-dock .chat-window { flex: 1; min-height: 260px; }

/* ===== 时光舱（推演进行中 / 抵达）—— 暗色驾驶舱 ===== */
.relasim-report-page.cockpit-mode { background: #0A0A0A; color: #DDD; }
.cockpit-mode .main-content { max-width: 1080px; padding: 34px 40px 60px; }
.cockpit { display: flex; flex-direction: column; min-height: calc(100vh - 160px); position: relative; }
/* 星场画布铺满视口，舱内内容浮于其上 */
.starfield { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
.cockpit > *:not(.starfield) { position: relative; z-index: 1; }

.cursor { color: #FF4500; animation: blink 1s step-end infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* 顶部旅程轨道 */
.voyage-head { display: flex; justify-content: flex-end; align-items: baseline; font-family: 'JetBrains Mono', monospace; margin-bottom: 18px; }
.voyage-tag { color: #FF4500; font-size: 0.8rem; letter-spacing: 1px; }
.voyage-meta { color: #666; font-size: 0.72rem; }
.voyage-rail { display: flex; align-items: flex-start; margin-bottom: 30px; }
.rail-node { display: flex; flex-direction: column; align-items: center; gap: 7px; cursor: default; min-width: 34px; }
.rail-dot { width: 12px; height: 12px; border: 1px solid #444; background: transparent; font-style: normal; font-size: 12px; line-height: 11px; color: #444; text-align: center; transition: all .3s; }
.rail-label { font-style: normal; font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; color: #555; white-space: nowrap; transition: color .3s; }
.rail-node.done { cursor: pointer; }
.rail-node.done .rail-dot { background: #FF4500; border-color: #FF4500; box-shadow: 0 0 8px rgba(255,69,0,.5); }
.rail-node.done .rail-label { color: #999; }
.rail-node.done:hover .rail-label { color: #FF4500; }
.rail-node.cur { cursor: pointer; }
.rail-node.cur .rail-dot { background: #fff; border-color: #fff; animation: breath 1.8s ease-in-out infinite; }
.rail-node.cur .rail-label { color: #fff; font-weight: 700; }
.rail-node.off .rail-dot { border-style: dashed; }
.rail-node.dest .rail-dot { border: none; width: auto; height: auto; background: none; color: #555; font-size: 14px; }
.rail-node.dest.blink .rail-dot { color: #FF4500; animation: blink 1s step-end infinite; }
.rail-node.dest.lit .rail-dot { color: #16a34a; }
.rail-node.dest.lit .rail-label { color: #16a34a; }
.rail-line { flex: 1; height: 1px; background: #2a2a2a; margin-top: 6px; transition: all .4s; }
.rail-line.lit { background: #FF4500; box-shadow: 0 0 6px rgba(255,69,0,.4); }
@keyframes breath { 0%,100%{ box-shadow: 0 0 0 0 rgba(255,69,0,.35);} 70%{ box-shadow: 0 0 0 8px rgba(255,69,0,0);} }

/* 中央：校准态 / 大时间标签 + 图谱主角 */
.cockpit-center { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.calibrating { text-align: center; padding: 60px 0; width: 100%; }
.calib-title { font-family: 'JetBrains Mono', monospace; font-size: clamp(2rem, 6vw, 3.4rem); font-weight: 600; letter-spacing: 2px; color: #fff; margin: 0 0 26px; }
.calib-scan { height: 1px; background: #222; position: relative; overflow: hidden; max-width: 560px; margin: 0 auto 22px; }
.calib-scan span { position: absolute; left: -40%; top: 0; height: 100%; width: 40%; background: linear-gradient(90deg, transparent, #FF4500, transparent); animation: scan-x 1.4s linear infinite; }
.calib-sub { font-family: 'JetBrains Mono', monospace; color: #777; font-size: 0.8rem; }
@keyframes scan-x { 0%{ left: -40%; } 100%{ left: 100%; } }

.big-time-wrap { perspective: 600px; margin-bottom: 14px; min-height: clamp(2.6rem, 7vw, 4rem); display: flex; align-items: center; }
.big-time { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: clamp(2rem, 6vw, 3.2rem); font-weight: 800; color: #FF4500; letter-spacing: 2px; animation: flip-in .55s ease both, time-glitch .6s steps(3) both; }
@keyframes flip-in { 0%{ transform: rotateX(-80deg) translateY(10px); opacity: 0; } 100%{ transform: rotateX(0) translateY(0); opacity: 1; } }
/* RGB 分离故障抖动：穿梭落地的瞬间 */
@keyframes time-glitch {
  0% { text-shadow: -4px 0 #3b82f6, 4px 0 #e11d48, 0 0 26px rgba(255,69,0,.5); }
  35% { text-shadow: 3px 0 #3b82f6, -3px 0 #e11d48, 0 0 26px rgba(255,69,0,.45); }
  70% { text-shadow: -1px 0 #3b82f6, 1px 0 #e11d48, 0 0 24px rgba(255,69,0,.4); }
  100% { text-shadow: 0 0 24px rgba(255,69,0,.35); }
}

.cockpit-graph { width: 100%; max-width: 900px; }
/* 穿梭瞬间：图谱缩放模糊爆闪 */
.cockpit-graph.warping { animation: graph-burst .75s ease; }
@keyframes graph-burst {
  0% { transform: scale(.96); filter: blur(2.5px) brightness(1.8); }
  55% { transform: scale(1.015); filter: blur(0) brightness(1.2); }
  100% { transform: scale(1); filter: none; }
}

/* 抵达面板 */
.arrive-panel { text-align: center; padding: 26px 0 6px; animation: fade-in-up .5s ease both; }
.arrive-tag { font-family: 'JetBrains Mono', monospace; color: #16a34a; font-size: 0.85rem; margin-bottom: 14px; letter-spacing: 1px; }
.arrive-outcome { display: inline-flex; align-items: baseline; gap: 12px; border: 1px solid #FF4500; background: rgba(255,69,0,.06); padding: 12px 22px; font-family: 'JetBrains Mono', monospace; margin-bottom: 20px; }
.ao-tag { color: #FF4500; font-size: 0.7rem; }
.ao-label { color: #fff; font-weight: 800; font-size: 1.1rem; }
.ao-pct { color: #FF4500; font-weight: 800; font-size: 1.1rem; }
.arrive-btn { display: block; margin: 0 auto; background: #FF4500; color: #fff; border: none; padding: 15px 34px; font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 0.95rem; cursor: pointer; transition: all .2s; }
.arrive-btn:hover { background: #fff; color: #000; }

/* 底部终端（最新一条打字机，column-reverse 自动钉底可上滚回看） */
.cockpit-term { background: #111; border: 1px solid #2a2a2a; padding: 14px 18px; font-family: 'JetBrains Mono', monospace; margin-top: 26px; }
.term-prompt { display: block; color: #FF4500; font-size: 0.72rem; margin-bottom: 10px; letter-spacing: 0.3px; }
.term-line { font-size: 0.84rem; line-height: 1.6; color: #BBB; }
.term-time { color: #666; }
.term-caret { color: #FF4500; animation: blink 1s step-end infinite; }
.term-line.scan { color: #666; font-size: 0.76rem; }
.term-line.ok { color: #16a34a; }
.term-line.busy { color: #c8763f; }
.term-history { display: flex; flex-direction: column-reverse; gap: 8px; max-height: 132px; overflow-y: auto; }

/* 白光过场：抵达 → 报告 */
.arrive-flash { position: fixed; inset: 0; background: #fff; z-index: 99; animation: flash-in .38s ease both; pointer-events: none; }
@keyframes flash-in { 0%{ opacity: 0; } 45%{ opacity: 1; } 100%{ opacity: 1; } }

/* 关系图谱可视化样式在 RelaSimGraph 组件内；此处仅控报告态间距 */
.report-graph { margin-bottom: 20px; }

/* 报告正文入场 */
.report-reveal { animation: fade-in-up .6s ease; }
.report-reveal .block { animation: fade-in-up .6s ease both; }
.report-reveal .block:nth-child(1) { animation-delay: .05s; }
.report-reveal .block:nth-child(2) { animation-delay: .12s; }
.report-reveal .block:nth-child(3) { animation-delay: .19s; }

@keyframes fade-in-up { 0%{ opacity:0; transform: translateY(12px); } 100%{ opacity:1; transform: translateY(0); } }

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

.block { margin-bottom: 36px; }
.block-meta { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.block-num { font-family: 'JetBrains Mono', monospace; font-weight: 800; color: #FF4500; font-size: 0.85rem; }
.block-name { font-size: 1.05rem; font-weight: 520; }

/* persons：紧凑一行卡，点击展开详情 */
.persons-list { display: flex; flex-direction: column; gap: 10px; }
.person-row { border: 1px solid #E5E5E5; padding: 12px 16px; cursor: pointer; transition: border-color .2s; }
.person-row:hover { border-color: #FF4500; }
.person-head { display: flex; align-items: center; gap: 12px; }
.person-avatar { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #fff; font-size: 1rem; flex-shrink: 0; }
.person-avatar.female { background: #e11d48; }
.person-avatar.male { background: #3b82f6; }
.person-avatar.unknown { background: #666; }
.person-id { flex: 1; display: flex; align-items: baseline; gap: 10px; min-width: 0; }
.person-name { font-weight: 600; font-size: 0.98rem; }
.person-sub { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #999; }
.person-expand { font-family: 'JetBrains Mono', monospace; color: #FF4500; font-weight: 800; font-size: 1rem; }
.attach-badge { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; padding: 3px 8px; border: 1px solid #DDD; color: #666; letter-spacing: 0.5px; }
.attach-badge.anxious { color: #e11d48; border-color: #fecdd3; background: #fff1f2; }
.attach-badge.avoidant { color: #3b82f6; border-color: #bfdbfe; background: #eff6ff; }
.attach-badge.fearful { color: #9333ea; border-color: #e9d5ff; background: #faf5ff; }
.attach-badge.secure { color: #16a34a; border-color: #bbf7d0; background: #f0fdf4; }
.person-fields { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; border-top: 1px dashed #E5E5E5; padding-top: 12px; }
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
.round-summary { font-size: 0.9rem; color: #333; line-height: 1.6; margin: 6px 0 0; }
.round-tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; }
.round-detail { margin-top: 12px; border-top: 1px dashed #E5E5E5; padding-top: 12px; }

/* 折叠控件 */
.clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.clamp-toggle { cursor: pointer; }
.expand-btn { background: none; border: 1px solid #DDD; color: #666; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; padding: 4px 12px; cursor: pointer; margin-top: 12px; transition: all .2s; }
.expand-btn:hover { border-color: #FF4500; color: #FF4500; }

.disclaimer { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #999; border-left: 2px solid #FF4500; padding-left: 12px; line-height: 1.6; margin: 40px 0; }

/* chat（右列 dock 内） */
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

@media (max-width: 1024px) {
  .report-cols { grid-template-columns: 1fr; }
  .chat-column { position: static; }
  .chat-dock { max-height: none; }
  .chat-dock .chat-window { min-height: 200px; }
}
@media (max-width: 768px) {
  .main-content { padding: 30px 20px 80px; }
  .two-col { grid-template-columns: 1fr; }
  .report-title { font-size: 1.8rem; }
}
</style>
