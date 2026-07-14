<template>
  <div class="graph-stage" :class="{ dark }">
    <!-- 当前时刻标签 -->
    <div class="graph-timebar" v-if="maxIndex >= 0">
      <span class="time-cur">◈ {{ curLabel }}</span>
      <span class="time-follow" v-if="following">▶ {{ t('relasim.timeNow') }}</span>
    </div>

    <!-- ===== 双人：档案对峙 + 关系通道 ===== -->
    <div v-if="isDuel" class="duel" :style="{ gap: duelGap + 'px' }">
      <!-- 左档案卡 -->
      <div v-if="nodeState(0) !== 'hidden'" class="dossier" :class="[left.gender, { warp: !!warp, ghost: nodeState(0) === 'ghost' }]">
        <div class="dossier-head">
          <span class="dossier-avatar" :style="nodeState(0) === 'ghost' ? {} : { background: gradFor(left.gender) }">{{ nodeState(0) === 'ghost' ? '?' : (left.name || '?').slice(0,1) }}</span>
          <div class="dossier-id">
            <div class="dossier-name">{{ left.name }}</div>
            <div class="dossier-meta" v-if="nodeState(0) === 'solid'">{{ genderSym(left.gender) }} {{ left.age || '—' }}</div>
          </div>
        </div>
        <template v-if="nodeState(0) === 'solid'">
          <div class="attach-chip" :style="{ color: attachColor(left.attachment_style), borderColor: attachColor(left.attachment_style) }">{{ attachLabel(left.attachment_style) }}</div>
          <div class="dossier-tags">
            <span v-for="(tag, i) in tagsOf(left)" :key="i" class="d-tag">#{{ tag }}</span>
          </div>
          <div class="dossier-trigger" v-if="left.triggers">⚠ {{ left.triggers }}</div>
        </template>
        <div v-else class="ghost-lines"><i></i><i></i><i></i></div>
      </div>

      <!-- 中央关系通道：上下两条定向能量带 -->
      <div class="channel">
        <div class="chan-band" v-if="ltr" @mouseenter="inspect = { type: 'edge', e: ltr }" @mouseleave="inspect = null">
          <div class="band-label">{{ left.name }} <b>→</b> {{ right.name }}</div>
          <div class="band-rel" :style="{ color: ltr.color }">{{ ltr.label }}</div>
          <div class="band-flow" :style="{ '--c': ltr.color }"><i></i><i></i><i></i></div>
          <div class="band-metrics">
            <span class="bm"><em>❤</em><i class="bm-bar"><b :style="{ width: pct(ltr.feeling.affection), background: '#FF4500' }"></b></i>{{ Math.round(ltr.feeling.affection||0) }}</span>
            <span class="bm"><em>⚡</em><i class="bm-bar"><b :style="{ width: pct(ltr.feeling.tension), background: '#e11d48' }"></b></i>{{ Math.round(ltr.feeling.tension||0) }}</span>
          </div>
        </div>
        <div class="chan-heart" v-if="eLimit > 0" :class="bondClass">{{ bondSymbol }}</div>
        <div class="chan-band rtl" v-if="rtl" @mouseenter="inspect = { type: 'edge', e: rtl }" @mouseleave="inspect = null">
          <div class="band-label">{{ right.name }} <b>→</b> {{ left.name }}</div>
          <div class="band-rel" :style="{ color: rtl.color }">{{ rtl.label }}</div>
          <div class="band-flow rev" :style="{ '--c': rtl.color }"><i></i><i></i><i></i></div>
          <div class="band-metrics">
            <span class="bm"><em>❤</em><i class="bm-bar"><b :style="{ width: pct(rtl.feeling.affection), background: '#FF4500' }"></b></i>{{ Math.round(rtl.feeling.affection||0) }}</span>
            <span class="bm"><em>⚡</em><i class="bm-bar"><b :style="{ width: pct(rtl.feeling.tension), background: '#e11d48' }"></b></i>{{ Math.round(rtl.feeling.tension||0) }}</span>
          </div>
        </div>
      </div>

      <!-- 右档案卡 -->
      <div v-if="nodeState(1) !== 'hidden'" class="dossier right" :class="[right.gender, { warp: !!warp, ghost: nodeState(1) === 'ghost' }]">
        <div class="dossier-head">
          <span class="dossier-avatar" :style="nodeState(1) === 'ghost' ? {} : { background: gradFor(right.gender) }">{{ nodeState(1) === 'ghost' ? '?' : (right.name || '?').slice(0,1) }}</span>
          <div class="dossier-id">
            <div class="dossier-name">{{ right.name }}</div>
            <div class="dossier-meta" v-if="nodeState(1) === 'solid'">{{ genderSym(right.gender) }} {{ right.age || '—' }}</div>
          </div>
        </div>
        <template v-if="nodeState(1) === 'solid'">
          <div class="attach-chip" :style="{ color: attachColor(right.attachment_style), borderColor: attachColor(right.attachment_style) }">{{ attachLabel(right.attachment_style) }}</div>
          <div class="dossier-tags">
            <span v-for="(tag, i) in tagsOf(right)" :key="i" class="d-tag">#{{ tag }}</span>
          </div>
          <div class="dossier-trigger" v-if="right.triggers">⚠ {{ right.triggers }}</div>
        </template>
        <div v-else class="ghost-lines"><i></i><i></i><i></i></div>
      </div>
    </div>

    <!-- ===== 多人：星系关系图（≥3人回退）===== -->
    <div v-else class="graph-canvas">
      <svg class="graph-svg" :viewBox="`0 0 ${W} ${H}`">
        <defs>
          <marker id="rg-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#999" />
          </marker>
          <radialGradient id="rg-grad-f" cx="35%" cy="30%" r="80%"><stop offset="0%" stop-color="#fb7185" /><stop offset="100%" stop-color="#be123c" /></radialGradient>
          <radialGradient id="rg-grad-m" cx="35%" cy="30%" r="80%"><stop offset="0%" stop-color="#60a5fa" /><stop offset="100%" stop-color="#1d4ed8" /></radialGradient>
          <radialGradient id="rg-grad-u" cx="35%" cy="30%" r="80%"><stop offset="0%" stop-color="#9ca3af" /><stop offset="100%" stop-color="#4b5563" /></radialGradient>
        </defs>
        <circle v-for="(d, i) in bgDots" :key="'bg' + i" :cx="d.x" :cy="d.y" r="1.1" class="bg-dot" :style="{ opacity: d.o, animationDelay: d.delay + 'ms' }" />
        <g v-for="e in shownEdges" :key="e.key">
          <path class="graph-edge-glow" :d="e.d" :style="{ stroke: e.color, strokeWidth: (e.width * 3.2) + 'px', animationDelay: (e.delay + 300) + 'ms' }" />
          <path class="graph-edge" :d="e.d" pathLength="1" marker-end="url(#rg-arrow)" :style="{ stroke: e.color, strokeWidth: e.width + 'px', animationDelay: e.delay + 'ms' }" />
          <path class="graph-edge-flow" :d="e.d" :style="{ animationDelay: (e.delay % 900) + 'ms' }" />
          <path class="graph-edge-hit" :d="e.d" @mouseenter="inspect = { type: 'edge', e }" @mouseleave="inspect = null" />
          <text class="graph-edge-label" :x="e.lx" :y="e.ly" text-anchor="middle" :style="{ animationDelay: (e.delay + 500) + 'ms' }">{{ e.label }}</text>
          <text class="graph-edge-vals" :x="e.lx" :y="e.ly + 13" text-anchor="middle" :style="{ animationDelay: (e.delay + 650) + 'ms' }">❤{{ Math.round(e.feeling.affection || 0) }} ⚡{{ Math.round(e.feeling.tension || 0) }}</text>
        </g>
        <template v-for="(nd, i) in nodes" :key="nd.person_id">
          <g v-if="nodeState(i) !== 'hidden'" class="graph-node" :class="{ ghost: nodeState(i) === 'ghost' }" :style="{ animationDelay: '0ms' }" @mouseenter="inspect = { type: 'person', p: nd }" @mouseleave="inspect = null">
            <template v-if="nodeState(i) === 'solid'">
              <circle :cx="nd.x" :cy="nd.y" :r="R + 17" class="orbit-ring" :style="{ animationDelay: (i * -3000) + 'ms' }" />
              <circle :cx="nd.x" :cy="nd.y" :r="R + 9" class="node-halo" :class="nd.gender" :style="{ animationDelay: (i * 700) + 'ms' }" />
              <circle :cx="nd.x" :cy="nd.y" :r="R + 5" fill="none" :stroke="attachColor(nd.attachment_style)" stroke-width="1.5" stroke-dasharray="4 3" class="graph-node-ring" />
              <circle :cx="nd.x" :cy="nd.y" :r="R" class="graph-node-circle" :fill="gradFor(nd.gender)" />
              <text :x="nd.x" :y="nd.y + 7" text-anchor="middle" class="graph-node-char">{{ (nd.name || '?').slice(0, 1) }}</text>
              <text :x="nd.x" :y="nd.y + R + 20" text-anchor="middle" class="graph-node-name">{{ nd.name }}</text>
              <text :x="nd.x" :y="nd.y + R + 34" text-anchor="middle" class="graph-node-sub">{{ genderSym(nd.gender) }} {{ nd.age || '—' }} · {{ attachLabel(nd.attachment_style) }}</text>
            </template>
            <template v-else>
              <circle :cx="nd.x" :cy="nd.y" :r="R" class="graph-node-ghost" />
              <text :x="nd.x" :y="nd.y + 7" text-anchor="middle" class="graph-node-char ghost-char">?</text>
              <text :x="nd.x" :y="nd.y + R + 20" text-anchor="middle" class="graph-node-name">{{ nd.name }}</text>
            </template>
          </g>
        </template>
      </svg>
    </div>

    <!-- 穿梭过场层（双人/多人共用） -->
    <div v-if="warp" :key="warp.key" class="warp-layer">
      <div class="warp-lines"></div>
      <div class="warp-label">
        <span class="warp-from">{{ warp.from }}</span>
        <span class="warp-arrow">≫</span>
        <span class="warp-to">{{ warp.to }}</span>
      </div>
    </div>

    <!-- 检视条 -->
    <div class="graph-inspector">
      <template v-if="inspect && inspect.type === 'person'">
        <span class="insp-name" :class="inspect.p.gender">{{ inspect.p.name }}</span>
        <span class="insp-kv"><i>性格</i>{{ inspect.p.personality || '—' }}</span>
        <span class="insp-kv"><i>情感需求</i>{{ inspect.p.emotional_needs || '—' }}</span>
        <span class="insp-kv"><i>雷区</i>{{ inspect.p.triggers || '—' }}</span>
      </template>
      <template v-else-if="inspect && inspect.type === 'edge'">
        <span class="insp-name edge">{{ inspect.e.sourceName }} → {{ inspect.e.targetName }}</span>
        <span class="insp-rel">{{ inspect.e.label }}</span>
        <span v-for="d in dims" :key="d.key" class="insp-dim">
          <i class="insp-dim-k">{{ t('relasim.' + d.i18n) }}</i>
          <i class="insp-dim-bar"><b :style="{ width: pct(inspect.e.feeling[d.key]), background: d.color }"></b></i>
          <i class="insp-dim-v">{{ Math.round(inspect.e.feeling[d.key] || 0) }}</i>
        </span>
      </template>
      <span v-else class="insp-hint">{{ t('relasim.inspectorHint') }}</span>
    </div>

    <!-- 时间轴滑块 -->
    <div class="time-scrub" v-if="maxIndex >= 0">
      <input class="scrub-range" type="range" :min="-1" :max="maxIndex" step="1" :value="timeIndex" @input="$emit('scrub', parseInt($event.target.value, 10))" />
      <button class="scrub-now" :class="{ active: following }" @click="$emit('now')">▶ {{ t('relasim.timeNow') }}</button>
    </div>
    <div class="scrub-ticks" v-if="maxIndex >= 0">
      <span v-for="tk in ticks" :key="tk.idx" class="scrub-tick" :class="{ cur: tk.idx === timeIndex, off: !tk.ready }" @click="tk.ready && $emit('scrub', tk.idx)">{{ tk.label }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  ticks: { type: Array, default: () => [] },
  timeIndex: { type: Number, default: -1 },
  maxIndex: { type: Number, default: -1 },
  following: { type: Boolean, default: false },
  warp: { type: Object, default: null },
  dark: { type: Boolean, default: false },
  // 建档揭晓门控：-1=全部显示；n=只显示前 n 个（ghost 为“候选态”上限）
  visibleNodes: { type: Number, default: -1 },
  ghostNodes: { type: Number, default: -1 },
  visibleEdges: { type: Number, default: -1 }
})
defineEmits(['scrub', 'now'])

// 揭晓门控计算
const nLimit = computed(() => (props.visibleNodes < 0 ? props.nodes.length : Math.max(0, props.visibleNodes)))
const gLimit = computed(() => (props.ghostNodes < 0 ? props.nodes.length : Math.max(nLimit.value, props.ghostNodes)))
const eLimit = computed(() => (props.visibleEdges < 0 ? props.edges.length : Math.max(0, props.visibleEdges)))
const shownEdges = computed(() => props.edges.slice(0, eLimit.value))
function nodeState(i) {
  if (i < nLimit.value) return 'solid'
  if (i < gLimit.value) return 'ghost'
  return 'hidden'
}

const { t } = useI18n()
const W = 760
const H = 340
const R = 30
const inspect = ref(null)

const ATTACH_COLORS = { secure: '#16a34a', anxious: '#e11d48', avoidant: '#3b82f6', fearful: '#9333ea' }
function attachColor(style) { return ATTACH_COLORS[style] || '#BBB' }
function attachLabel(style) {
  const map = { secure: t('relasim.attachmentSecure'), anxious: t('relasim.attachmentAnxious'), avoidant: t('relasim.attachmentAvoidant'), fearful: t('relasim.attachmentFearful') }
  return map[style] || style || '—'
}
function genderSym(g) { return g === 'female' ? '♀' : g === 'male' ? '♂' : '·' }
function gradFor(g) { return `linear-gradient(135deg, ${g === 'female' ? '#fb7185,#be123c' : g === 'male' ? '#60a5fa,#1d4ed8' : '#9ca3af,#4b5563'})` }
function pct(v) { return Math.max(0, Math.min(100, v || 0)) + '%' }
// 性格 → 关键词标签（按标点切句取前几段，压短）
function tagsOf(p) {
  const src = p.personality || ''
  return src.split(/[，,。；;、\s]+/).map(s => s.trim()).filter(s => s.length >= 2 && s.length <= 6).slice(0, 3)
}

// 双人判定
const isDuel = computed(() => props.nodes.length === 2)
const left = computed(() => props.nodes[0] || {})
const right = computed(() => props.nodes[1] || {})
// 按名字方向分配上下能量带（受揭晓门控约束）
const ltr = computed(() => {
  const e = props.edges.find(x => x.sourceName === left.value.name && x.targetName === right.value.name)
  return e && props.edges.indexOf(e) < eLimit.value ? e : null
})
const rtl = computed(() => {
  const e = props.edges.find(x => x.sourceName === right.value.name && x.targetName === left.value.name)
  return e && props.edges.indexOf(e) < eLimit.value ? e : null
})
// 两卡间距随双向好感均值变化：越亲近越靠拢（80~360px）
const duelGap = computed(() => {
  const a = ((ltr.value?.feeling.affection || 50) + (rtl.value?.feeling.affection || 50)) / 2
  return Math.round(360 - a / 100 * 280)
})
// 中央羁绊符号：按张力/好感给情绪
const avgTension = computed(() => ((ltr.value?.feeling.tension || 0) + (rtl.value?.feeling.tension || 0)) / 2)
const avgAff = computed(() => ((ltr.value?.feeling.affection || 0) + (rtl.value?.feeling.affection || 0)) / 2)
const bondClass = computed(() => avgTension.value >= 65 ? 'strain' : avgAff.value >= 60 ? 'warm' : 'neutral')
const bondSymbol = computed(() => avgTension.value >= 65 ? '⚡' : avgAff.value >= 60 ? '♥' : '◇')

const bgDots = computed(() => Array.from({ length: 46 }, (_, i) => ({
  x: 18 + ((i * 137 + 53) % (W - 36)), y: 14 + ((i * 79 + 31) % (H - 28)),
  o: 0.12 + ((i * 37) % 10) / 42, delay: (i * 233) % 3600
})))

const dims = [
  { key: 'affection', i18n: 'dimAffection', color: '#FF4500' },
  { key: 'trust', i18n: 'dimTrust', color: '#3b82f6' },
  { key: 'dependence', i18n: 'dimDependence', color: '#9333ea' },
  { key: 'tension', i18n: 'dimTension', color: '#e11d48' },
  { key: 'commitment', i18n: 'dimCommitment', color: '#16a34a' }
]

const curLabel = computed(() => {
  const tk = props.ticks.find(x => x.idx === props.timeIndex)
  return tk ? tk.label : ''
})
</script>

<style scoped>
.graph-stage { border: 1px solid #E5E5E5; background: #FAFAFA; padding: 10px; position: relative; }

.graph-timebar { display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; padding: 2px 4px 8px; }
.time-cur { color: #000; font-weight: 700; letter-spacing: 0.5px; }
.time-follow { color: #FF4500; animation: blink-soft 1.6s ease-in-out infinite; }
@keyframes blink-soft { 0%,100%{opacity:1} 50%{opacity:.35} }

/* ===== 双人档案对峙 ===== */
.duel { position: relative; display: flex; align-items: center; justify-content: center; padding: 26px 6px; transition: gap .8s cubic-bezier(.22,1,.36,1); }
.dossier { width: 190px; flex-shrink: 0; border: 1px solid #E2E2E2; background: #fff; padding: 16px; transition: transform .8s cubic-bezier(.22,1,.36,1); }
.dossier.warp { animation: dossier-jolt .7s ease; }
@keyframes dossier-jolt { 0%{ transform: translateX(0); } 30%{ transform: translateX(-4px); } 60%{ transform: translateX(3px); } 100%{ transform: translateX(0); } }
.dossier.right { text-align: right; }
/* 候选幽灵态：识别中的人物（虚线框 + ? 头像 + 骨架行） */
.dossier.ghost { border-style: dashed; opacity: .8; animation: ghost-in .4s ease both; }
.dossier.ghost .dossier-avatar { background: transparent; border: 1.5px dashed #999; color: #999; }
.dossier.ghost .dossier-name { color: #999; }
.ghost-lines { display: flex; flex-direction: column; gap: 8px; margin-top: 4px; }
.ghost-lines i { display: block; height: 8px; background: linear-gradient(90deg, rgba(150,150,150,.18), rgba(150,150,150,.34), rgba(150,150,150,.18)); background-size: 200% 100%; animation: ghost-shimmer 1.2s linear infinite; }
.ghost-lines i:nth-child(2) { width: 72%; }
.ghost-lines i:nth-child(3) { width: 48%; }
@keyframes ghost-in { from { opacity: 0; transform: translateY(6px); } to { opacity: .8; transform: none; } }
@keyframes ghost-shimmer { 0% { background-position: 0 0; } 100% { background-position: -200% 0; } }
.dossier-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.dossier.right .dossier-head { flex-direction: row-reverse; }
.dossier-avatar { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #fff; font-size: 1.15rem; flex-shrink: 0; box-shadow: 0 0 14px rgba(255,69,0,.25); }
.dossier-name { font-weight: 700; font-size: 1rem; }
.dossier-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #999; }
.attach-chip { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; padding: 2px 8px; border: 1px solid; margin-bottom: 10px; }
.dossier-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
.dossier.right .dossier-tags { justify-content: flex-end; }
.d-tag { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; color: #FF4500; background: rgba(255,69,0,.08); padding: 2px 6px; }
.dossier-trigger { font-size: 0.68rem; color: #e11d48; line-height: 1.5; }

/* 中央关系通道 */
.channel { flex: 1; min-width: 150px; display: flex; flex-direction: column; gap: 8px; align-items: stretch; }
.chan-band { border: 1px solid #EAEAEA; background: #FBFBFB; padding: 8px 12px; cursor: pointer; transition: border-color .2s; animation: band-in .5s ease both; }
.chan-band:hover { border-color: #FF4500; }
@keyframes band-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.band-label { font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; color: #888; }
.band-label b { color: #FF4500; }
.band-rel { font-size: 0.8rem; font-weight: 600; margin: 2px 0 6px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; max-width: 100%; animation: rel-type 1s steps(22) both .2s; }
@keyframes rel-type { from { max-width: 0; } to { max-width: 100%; } }
.band-flow { position: relative; height: 3px; background: linear-gradient(90deg, rgba(0,0,0,.05), rgba(0,0,0,.12)); overflow: hidden; margin-bottom: 8px; }
.band-flow i { position: absolute; top: -1px; width: 16px; height: 5px; background: linear-gradient(90deg, transparent, var(--c), transparent); animation: flow-x 1.1s linear infinite; }
.band-flow i:nth-child(2){ animation-delay: .37s; } .band-flow i:nth-child(3){ animation-delay: .74s; }
.band-flow.rev i { animation-name: flow-x-rev; }
@keyframes flow-x { 0%{ left: -16px; } 100%{ left: 100%; } }
@keyframes flow-x-rev { 0%{ left: 100%; } 100%{ left: -16px; } }
.band-metrics { display: flex; gap: 14px; }
.bm { display: inline-flex; align-items: center; gap: 5px; font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; color: #555; }
.bm em { font-style: normal; }
.bm-bar { width: 46px; height: 5px; background: #EEE; display: inline-block; overflow: hidden; }
.bm-bar b { display: block; height: 100%; transition: width .7s ease; transform-origin: left; animation: bar-grow .9s ease both .35s; }
@keyframes bar-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.chan-heart { text-align: center; font-size: 1.3rem; }
.chan-heart.warm { color: #FF4500; animation: heart-beat 1.4s ease-in-out infinite; }
.chan-heart.strain { color: #e11d48; animation: heart-shake .5s ease-in-out infinite; }
.chan-heart.neutral { color: #BBB; }
@keyframes heart-beat { 0%,100%{ transform: scale(1); } 50%{ transform: scale(1.25); } }
@keyframes heart-shake { 0%,100%{ transform: translateX(0) rotate(0); } 25%{ transform: translateX(-2px) rotate(-8deg); } 75%{ transform: translateX(2px) rotate(8deg); } }

/* ===== 多人星系图 ===== */
.graph-canvas { position: relative; overflow: hidden; }
.graph-svg { width: 100%; display: block; }
.bg-dot { fill: #C8C8C8; animation: dot-twinkle 3.6s ease-in-out infinite; }
@keyframes dot-twinkle { 0%,100%{ opacity: .1; } 50%{ opacity: .5; } }
.graph-edge-glow { fill: none; opacity: 0; filter: blur(4px); animation: glow-in .8s ease forwards; }
@keyframes glow-in { to { opacity: .3; } }
.graph-edge { fill: none; stroke-dasharray: 1; stroke-dashoffset: 1; animation: edge-draw .9s ease forwards; transition: stroke .8s ease, stroke-width .8s ease; }
.graph-edge-flow { fill: none; stroke: #FF4500; stroke-width: 1.8; stroke-dasharray: 3 15; stroke-linecap: round; opacity: .8; animation: edge-flow 1s linear infinite; pointer-events: none; }
@keyframes edge-flow { to { stroke-dashoffset: -18; } }
.graph-edge-hit { fill: none; stroke: transparent; stroke-width: 16; pointer-events: stroke; cursor: pointer; }
.graph-edge-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; fill: #666; opacity: 0; animation: g-fade-in .5s ease forwards; pointer-events: none; }
.graph-edge-vals { font-family: 'JetBrains Mono', monospace; font-size: 9px; fill: #999; opacity: 0; animation: g-fade-in .5s ease forwards; pointer-events: none; }
.graph-node { opacity: 0; transform: scale(.4); transform-box: fill-box; transform-origin: center; animation: done-pop .45s ease forwards; cursor: pointer; }
.orbit-ring { fill: none; stroke: #D8D8D8; stroke-width: 1; stroke-dasharray: 3 7; transform-box: fill-box; transform-origin: center; animation: orbit-spin 16s linear infinite; }
@keyframes orbit-spin { to { transform: rotate(360deg); } }
.node-halo { fill: none; stroke: rgba(255,69,0,.3); stroke-width: 5; transform-box: fill-box; transform-origin: center; animation: halo-pulse 2.6s ease-in-out infinite; }
.node-halo.female { stroke: rgba(225,29,72,.35); }
.node-halo.male { stroke: rgba(59,130,246,.35); }
@keyframes halo-pulse { 0%,100%{ transform: scale(.9); opacity: .2; } 50%{ transform: scale(1.1); opacity: .8; } }
.graph-node-ring { opacity: .9; }
.graph-node-circle { stroke: #fff; stroke-width: 2; }
.graph-node-char { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; fill: #fff; pointer-events: none; }
.graph-node-name { font-family: 'JetBrains Mono', monospace; font-size: 11.5px; font-weight: 700; fill: #333; }
.graph-node-sub { font-family: 'JetBrains Mono', monospace; font-size: 9px; fill: #999; }
/* SVG 幽灵候选节点 */
.graph-node-ghost { fill: none; stroke: #999; stroke-width: 1.5; stroke-dasharray: 5 4; }
.ghost-char { fill: #999; }
.graph-node.ghost .graph-node-name { fill: #999; }
@keyframes edge-draw { to { stroke-dashoffset: 0; } }
@keyframes g-fade-in { to { opacity: 1; } }
@keyframes done-pop { 0%{ opacity:0; transform: scale(.4); } 100%{ opacity:1; transform: scale(1); } }

/* 穿梭过场 */
.warp-layer { position: absolute; inset: 0; pointer-events: none; display: flex; align-items: center; justify-content: center; }
.warp-lines { position: absolute; inset: 0; background: repeating-linear-gradient(90deg, transparent 0 26px, rgba(255,69,0,.14) 26px 28px); animation: warp-sweep .7s linear forwards; }
.warp-label { position: relative; display: flex; align-items: center; gap: 14px; font-family: 'JetBrains Mono', monospace; font-weight: 800; background: rgba(255,255,255,.88); padding: 8px 18px; border: 1px solid #FF4500; }
.warp-from { font-size: 1rem; color: #999; animation: warp-out .7s ease forwards; }
.warp-arrow { color: #FF4500; font-size: 1.2rem; animation: blink-soft .35s ease-in-out infinite; }
.warp-to { font-size: 1.35rem; color: #000; animation: warp-in .7s ease both; }
@keyframes warp-sweep { 0%{ transform: translateX(0); opacity: 1; } 100%{ transform: translateX(-56px); opacity: 0; } }
@keyframes warp-out { 0%{ transform: translateY(0) rotateX(0); opacity: 1; } 100%{ transform: translateY(-10px) rotateX(70deg); opacity: .3; } }
@keyframes warp-in { 0%{ transform: translateY(12px) rotateX(-70deg); opacity: 0; } 55%{ transform: translateY(0) rotateX(0); opacity: 1; } 100%{ opacity: 1; } }

/* 检视条 */
.graph-inspector { min-height: 44px; margin-top: 8px; border: 1px dashed #E0E0E0; background: #fff; padding: 8px 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; }
.insp-hint { color: #BBB; }
.insp-name { color: #fff; padding: 2px 8px; font-weight: 700; background: #666; }
.insp-name.female { background: #e11d48; }
.insp-name.male { background: #3b82f6; }
.insp-name.edge { background: #000; }
.insp-rel { color: #FF4500; font-weight: 700; }
.insp-kv { color: #444; display: inline-flex; gap: 6px; max-width: 100%; }
.insp-kv i { font-style: normal; color: #999; flex-shrink: 0; }
.insp-dim { display: inline-flex; align-items: center; gap: 5px; }
.insp-dim-k { font-style: normal; color: #999; }
.insp-dim-bar { font-style: normal; width: 52px; height: 6px; background: #F0F0F0; display: inline-block; overflow: hidden; }
.insp-dim-bar b { display: block; height: 100%; transition: width .5s ease; }
.insp-dim-v { font-style: normal; color: #333; font-weight: 700; min-width: 20px; }

/* 时间轴滑块 */
.time-scrub { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
.scrub-range { flex: 1; -webkit-appearance: none; appearance: none; height: 4px; background: #E5E5E5; outline: none; cursor: pointer; }
.scrub-range::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 16px; height: 16px; background: #FF4500; border: 2px solid #fff; box-shadow: 0 0 0 1px #FF4500; cursor: grab; }
.scrub-range::-moz-range-thumb { width: 14px; height: 14px; background: #FF4500; border: 2px solid #fff; box-shadow: 0 0 0 1px #FF4500; border-radius: 0; cursor: grab; }
.scrub-now { background: none; border: 1px solid #DDD; color: #999; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; padding: 4px 10px; cursor: pointer; transition: all .2s; white-space: nowrap; }
.scrub-now.active { border-color: #FF4500; color: #FF4500; }
.scrub-now:hover { border-color: #FF4500; color: #FF4500; }
.scrub-ticks { display: flex; justify-content: space-between; margin-top: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; }
.scrub-tick { color: #BBB; cursor: pointer; transition: color .2s; }
.scrub-tick:hover { color: #FF4500; }
.scrub-tick.cur { color: #FF4500; font-weight: 800; }
.scrub-tick.off { color: #E5E5E5; cursor: not-allowed; }

/* ===== 暗色驾驶舱模式 ===== */
.graph-stage.dark { background: rgba(15,15,15,.72); border-color: #333; backdrop-filter: blur(2px); }
.dark .time-cur { color: #EEE; }
/* 双人暗色 */
.dark .dossier { background: rgba(20,20,22,.85); border-color: #333; }
.dark .dossier.ghost { border-color: #555; }
.dark .dossier.ghost .dossier-avatar { border-color: #666; color: #777; }
.dark .dossier-name { color: #EEE; }
.dark .dossier-meta { color: #888; }
.dark .d-tag { color: #ff7a45; background: rgba(255,69,0,.14); }
.dark .chan-band { background: rgba(18,18,20,.8); border-color: #333; }
.dark .band-label { color: #999; }
.dark .band-flow { background: linear-gradient(90deg, rgba(255,255,255,.05), rgba(255,255,255,.12)); }
.dark .bm { color: #AAA; }
.dark .bm-bar { background: #2a2a2a; }
/* 多人暗色 */
.dark .bg-dot { fill: #555; }
.dark .graph-edge-flow { stroke: #fff; }
.dark .graph-node-circle { stroke: #1a1a1a; filter: drop-shadow(0 0 8px rgba(255,255,255,.3)); }
.dark .orbit-ring { stroke: #3a3a3a; }
.dark .graph-node-ring { opacity: 1; filter: drop-shadow(0 0 4px rgba(255,69,0,.3)); }
.dark .graph-node-name { fill: #EEE; }
.dark .graph-node-sub { fill: #888; }
.dark .graph-edge-label { fill: #AAA; }
.dark .graph-edge-vals { fill: #777; }
.dark .graph-inspector { background: rgba(13,13,13,.8); border-color: #333; }
.dark .insp-hint { color: #555; }
.dark .insp-kv { color: #BBB; }
.dark .insp-kv i { color: #666; }
.dark .insp-dim-k { color: #777; }
.dark .insp-dim-v { color: #DDD; }
.dark .insp-dim-bar { background: #222; }
.dark .scrub-range { background: #333; }
.dark .scrub-now { border-color: #444; color: #777; }
.dark .scrub-now.active, .dark .scrub-now:hover { border-color: #FF4500; color: #FF4500; }
.dark .scrub-tick { color: #555; }
.dark .scrub-tick:hover { color: #FF4500; }
.dark .scrub-tick.cur { color: #FF4500; }
.dark .scrub-tick.off { color: #2a2a2a; }
.dark .warp-label { background: rgba(10,10,10,.85); border-color: #FF4500; }
.dark .warp-from { color: #666; }
.dark .warp-to { color: #fff; }
.dark .warp-lines { background: repeating-linear-gradient(90deg, transparent 0 26px, rgba(255,69,0,.22) 26px 28px); }
</style>
