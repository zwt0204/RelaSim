<template>
  <div class="relasim-page">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-brand" @click="goHome">RELASIM<span class="brand-suffix">关系推演</span></div>
      <div class="nav-links">
        <LanguageSwitcher />
        <span class="nav-divider">|</span>
        <span class="nav-back" @click="goHome">{{ $t('relasim.navBack') }} ↗</span>
      </div>
    </nav>

    <div class="main-content">
      <!-- Hero -->
      <section class="hero">
        <div class="hero-tag-row">
          <span class="orange-tag">◇ {{ $t('relasim.brand') }}</span>
          <span class="hero-tip" v-if="!expanded">{{ $t('relasim.heroTag') }}</span>
        </div>
        <h1 class="hero-title" ref="heroTitleRef">
          <span class="t1">{{ $t('relasim.heroTitle1') }}</span><br>
          <span class="t2">SOCIAL&nbsp;SIMULATION<span class="cursor">_</span></span>
        </h1>
        <p class="hero-desc">{{ $t('relasim.heroDesc') }}</p>
        <p class="disclaimer">{{ $t('relasim.disclaimerShort') }}</p>
      </section>

      <!-- 种子材料输入 -->
      <section class="form-section">
        <div class="form-meta">
          <span class="section-num">01</span>
          <span class="section-name">{{ $t('relasim.formTitle') }}</span>
        </div>

        <div class="console-box">
          <!-- 大文本区 -->
          <div class="console-section seed-section">
            <div class="console-header">
              <span>{{ $t('relasim.formSeedLabel') }}</span>
              <button class="demo-btn" @click="fillDemo" v-if="!loading">{{ $t('relasim.useDemo') }}</button>
            </div>
            <div class="input-wrapper">
              <textarea
                v-model="seed"
                class="code-input"
                :placeholder="$t('relasim.formSeedPlaceholder')"
                :disabled="loading"
              ></textarea>
              <span class="model-badge">{{ modelBadge }}</span>
            </div>
            <div class="seed-error" v-if="showSeedError || errorMsg">✕ {{ errorMsg || $t('relasim.seedTooShort') }}</div>
          </div>

          <div class="console-divider"><span>+</span></div>

          <!-- 补充资料上传（对话记录等，可选） -->
          <div class="console-section">
            <div class="console-header">
              <span>{{ $t('relasim.uploadTitle') }}</span>
              <span class="upload-hint">{{ $t('relasim.uploadHint') }}</span>
            </div>
            <div class="upload-area">
              <input
                ref="fileInput"
                type="file"
                multiple
                accept=".txt,.md,.markdown,.pdf,.docx,.doc,.csv,.json,.log,.png,.jpg,.jpeg,.webp,.gif,.bmp"
                class="upload-input"
                @change="onFilesPicked"
              />
              <button class="upload-btn" @click="fileInput && fileInput.click()" :disabled="loading">
                ↑ {{ $t('relasim.uploadBtn') }}
              </button>
              <div class="upload-chips" v-if="attachments.length">
                <span v-for="(a, i) in attachments" :key="i" class="upload-chip" :class="{ err: a.error }">
                  <b>{{ a.name }}</b>
                  <i v-if="a.parsing" class="chip-status">{{ $t('relasim.uploadParsing') }}</i>
                  <i v-else-if="a.error" class="chip-status">✕ {{ a.error }}</i>
                  <i v-else class="chip-status ok">{{ a.chars }}{{ $t('relasim.charsUnit') }}{{ a.truncated ? '+' : '' }}</i>
                  <em class="chip-remove" @click="removeAttachment(i)" v-if="!a.parsing">✕</em>
                </span>
              </div>
            </div>
          </div>

          <div class="console-divider"><span>+</span></div>

          <!-- 推演诉求 -->
          <div class="console-section">
            <div class="console-header">
              <span>{{ $t('relasim.formQueryLabel') }}</span>
            </div>
            <div class="input-wrapper">
              <textarea
                v-model="query"
                class="code-input code-input-short"
                :placeholder="$t('relasim.formQueryPlaceholder')"
                :disabled="loading"
              ></textarea>
            </div>
          </div>

          <div class="console-divider"><span>+</span></div>

          <!-- 参数 -->
          <div class="console-section params-row">
            <div class="param-block">
              <label class="param-label">{{ $t('relasim.formRoundsLabel') }}</label>
              <div class="stepper">
                <button class="stepper-btn" @click="rounds = Math.max(1, rounds - 1)" :disabled="loading">−</button>
                <span class="stepper-val">{{ rounds }}</span>
                <button class="stepper-btn" @click="rounds = Math.min(20, rounds + 1)" :disabled="loading">+</button>
              </div>
              <span class="param-suffix">{{ $t('relasim.roundsSuffix') }}</span>
            </div>
            <div class="param-divider"></div>
            <div class="param-block">
              <label class="param-label">{{ $t('relasim.formTimeUnitLabel') }}</label>
              <div class="unit-toggle">
                <button
                  class="unit-opt"
                  :class="{ active: timeUnit === '周' || timeUnit === 'week' }"
                  @click="setUnit('week')"
                >{{ isZh ? $t('relasim.unitWeek') : 'WEEK' }}</button>
                <button
                  class="unit-opt"
                  :class="{ active: timeUnit === '月' || timeUnit === 'month' }"
                  @click="setUnit('month')"
                >{{ isZh ? $t('relasim.unitMonth') : 'MONTH' }}</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 事件注入 -->
      <section class="form-section">
        <div class="form-meta">
          <span class="section-num">02</span>
          <span class="section-name">{{ $t('relasim.eventsTitle') }}</span>
          <span class="section-hint">{{ $t('relasim.eventsHint') }}</span>
        </div>

        <div class="events-list">
          <div v-for="(ev, i) in events" :key="i" class="event-row">
            <div class="event-round">
              <label>{{ $t('relasim.eventRound') }}</label>
              <input
                type="number"
                v-model.number="ev.round_index"
                min="0"
                :max="rounds - 1"
                :disabled="loading"
                class="event-num"
              />
            </div>
            <input
              v-model="ev.description"
              class="event-desc"
              :placeholder="$t('relasim.eventDescPlaceholder')"
              :disabled="loading"
            />
            <button class="event-remove" @click="removeEvent(i)" :disabled="loading">− {{ $t('relasim.eventRemove') }}</button>
          </div>

          <button class="event-add" @click="addEvent" :disabled="loading || events.length >= rounds">
            {{ $t('relasim.eventAdd') }}
          </button>
        </div>
      </section>

      <!-- 提交按钮 -->
      <section class="submit-section">
        <button
          class="start-btn"
          :class="{ pulsing: canSubmit && !loading }"
          :disabled="loading"
          @click="start"
        >
          <span class="btn-label">{{ loading ? $t('relasim.submitting') : $t('relasim.submit') }}</span>
          <span class="btn-arrow">→</span>
        </button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { runRelaSim, getRelaSimStatus, getRelaSimResult, uploadRelaSimMaterial } from '../api/relasim'

const router = useRouter()
const { locale, t } = useI18n()
const isZh = computed(() => locale.value === 'zh')

const seed = ref('')
const query = ref('')
const rounds = ref(3)
const timeUnit = ref('周')
const events = ref([])
const loading = ref(false)
const errorMsg = ref('')
const heroTitleRef = ref(null)

const modelBadge = computed(() => {
  if (isZh.value) return `${rounds.value} 个 ${timeUnit.value === '月' ? '月' : '周'} 的关系演化`
  return `${rounds.value} ${timeUnit.value === '月' ? 'MONTH' : 'WEEK'}S · RELATIONSHIP EVOLUTION`
})

const canSubmit = computed(() => seed.value.trim().length > 20)
// 用户已输入但不足 20 字时给出可见提示（避免「点了没反应」）
const showSeedError = computed(() => !canSubmit.value && seed.value.trim().length > 0 && !loading.value)

const DEMO_SEED = `林然（女，24 岁）和陈默（男，25 岁）是大学同班同学，毕业两年一直是无话不谈的好朋友。
林然性格开朗外向，情绪表达直接，遇事喜欢找人倾诉，很在意对方的即时回应，一旦对方冷淡就会胡思乱想。她其实这一年多渐渐对陈默动了心，但怕破坏现在的关系不敢说。
陈默偏理性内敛，习惯把感受藏在心里，遇到亲密话题会本能地转移或用玩笑带过，他也隐约感觉到林然的心意，但因为上一段感情受过伤，对开始新关系很犹豫。
两人几乎每天都会聊天，周末常一起吃饭看电影，共同朋友都觉得他们像情侣。最近陈默拿到了一个去另一个城市工作的 offer，还没告诉林然。`

function fillDemo() {
  seed.value = DEMO_SEED
  query.value = isZh.value
    ? '如果接下来半年林然主动一些，他们最终会在一起还是回到纯友谊？'
    : 'If Lin Ran takes more initiative over the next six months, will they end up together or return to friendship?'
  events.value = [
    { round_index: 3, description: isZh.value ? '陈默拿到了去另一个城市的 offer，决定接受' : 'Chen Mo gets an out-of-town job offer and decides to take it' }
  ]
}

function setUnit(u) {
  timeUnit.value = u === 'week' ? (isZh.value ? '周' : 'week') : (isZh.value ? '月' : 'month')
}

function addEvent() {
  events.value.push({ round_index: Math.min(rounds.value - 1, events.value.length + 1), description: '' })
}
function removeEvent(i) {
  events.value.splice(i, 1)
}

// ===== 补充资料上传：选中即解析，成功后随 run 一并提交 =====
const attachments = ref([]) // { name, text, chars, truncated, parsing, error }
const fileInput = ref(null)
const parsingCount = computed(() => attachments.value.filter(a => a.parsing).length)
async function onFilesPicked(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  for (const f of files) {
    if (attachments.value.length >= 10) break
    const item = { name: f.name, text: '', chars: 0, truncated: false, parsing: true, error: '' }
    attachments.value.push(item)
    try {
      const res = await uploadRelaSimMaterial(f)
      if (res && res.success && res.data) {
        item.text = res.data.text
        item.chars = res.data.chars
        item.truncated = !!res.data.truncated
      } else {
        item.error = (res && res.error) || t('relasim.uploadFailed')
      }
    } catch (err) {
      item.error = (err && err.message) || t('relasim.uploadFailed')
    } finally {
      item.parsing = false
    }
  }
}
function removeAttachment(i) {
  attachments.value.splice(i, 1)
}

let pollTimer = null
async function start() {
  if (loading.value) return
  if (!canSubmit.value) {
    errorMsg.value = t('relasim.seedTooShort') || t('relasim.errorSeedRequired')
    return
  }
  errorMsg.value = ''
  if (parsingCount.value > 0) {
    errorMsg.value = t('relasim.uploadParsing')
    return
  }
  loading.value = true
  try {
    const res = await runRelaSim({
      seed_material: seed.value,
      prediction_query: query.value,
      rounds: rounds.value,
      time_unit: timeUnit.value,
      events: events.value,
      attachments: attachments.value
        .filter(a => !a.error && !a.parsing && a.text)
        .map(a => ({ name: a.name, text: a.text }))
    })
    if (!res || !res.success || !res.data || !res.data.task_id) {
      loading.value = false
      errorMsg.value = t('relasim.startFailed')
      return
    }
    const taskId = res.data.task_id
    router.push({ name: 'RelaSimRun', params: { taskId } })
  } catch (e) {
    console.error('启动推演失败', e)
    loading.value = false
    errorMsg.value = t('relasim.startFailed')
  }
}

// 编辑种子材料即清除错误
watch(seed, () => { if (errorMsg.value) errorMsg.value = '' })

function goHome() {
  router.push('/')
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.relasim-page {
  min-height: 100vh;
  background: #FFFFFF;
  color: #000000;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* 导航 */
.navbar {
  height: 60px;
  background: #000;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.1rem;
  cursor: pointer;
}
.brand-suffix {
  color: #FF4500;
  font-weight: 500;
  letter-spacing: 1px;
}
.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.nav-divider { color: #444; }
.nav-back { cursor: pointer; transition: color .2s; }
.nav-back:hover { color: #FF4500; }

/* 主内容 */
.main-content {
  max-width: 860px;
  margin: 0 auto;
  padding: 70px 40px 120px;
}

/* Hero */
.hero { margin-bottom: 70px; }
.hero-tag-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
}
.orange-tag {
  background: #FF4500;
  color: #fff;
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}
.hero-tip { color: #999; letter-spacing: 0.5px; }
.hero-title {
  font-size: clamp(2.6rem, 6vw, 4.5rem);
  line-height: 1.15;
  font-weight: 500;
  margin: 0 0 30px 0;
  letter-spacing: -2px;
}
.hero-title .t1 { color: #000; }
.hero-title .t2 {
  display: inline-block;
  background: linear-gradient(90deg, #000 0%, #6b6b6b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -1px;
  font-weight: 600;
}
.cursor {
  color: #FF4500;
  -webkit-text-fill-color: #FF4500;
  animation: blink 1s step-end infinite;
  font-weight: 700;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: #666;
  max-width: 640px;
  margin: 0 0 24px;
  text-align: justify;
}
.disclaimer {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #999;
  border-left: 2px solid #FF4500;
  padding-left: 12px;
  line-height: 1.6;
}

/* form 区块 */
.form-section { margin-bottom: 50px; }
.form-meta {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.section-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  color: #FF4500;
  font-size: 0.95rem;
}
.section-name {
  font-size: 1.15rem;
  font-weight: 520;
  letter-spacing: 0.5px;
}
.section-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #999;
}

/* 控制台盒 */
.console-box {
  border: 1px solid #CCC;
  padding: 8px;
}
.console-section { padding: 18px 20px; }
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #666;
}
.demo-btn {
  background: none;
  border: 1px solid #DDD;
  padding: 3px 10px;
  font-family: inherit;
  font-size: 0.72rem;
  color: #666;
  cursor: pointer;
  transition: all .2s;
}
.demo-btn:hover { border-color: #FF4500; color: #FF4500; }
.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}
.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 18px 20px;
  font-family: 'JetBrains Mono', 'Noto Sans SC', monospace;
  font-size: 0.88rem;
  line-height: 1.7;
  resize: vertical;
  outline: none;
  min-height: 160px;
  color: #000;
  box-sizing: border-box;
}
.code-input-short { min-height: 70px; }
.code-input:focus { caret-color: #FF4500; }
.model-badge {
  position: absolute;
  bottom: 8px;
  right: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  color: #BBB;
  pointer-events: none;
}

/* 参数行 */
.params-row {
  display: flex;
  align-items: center;
}
.param-block {
  display: flex;
  align-items: center;
  gap: 12px;
}
.param-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #666;
  letter-spacing: 0.5px;
}
.stepper {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid #DDD;
}
.stepper-btn {
  background: none;
  border: none;
  padding: 6px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  cursor: pointer;
  color: #000;
  transition: all .2s;
}
.stepper-btn:hover { background: #FF4500; color: #fff; }
.stepper-val {
  padding: 6px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 1rem;
  min-width: 30px;
  text-align: center;
  border-left: 1px solid #DDD;
  border-right: 1px solid #DDD;
}
.param-suffix { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #999; }
.param-divider {
  width: 1px;
  height: 28px;
  background: #EEE;
  margin: 0 28px;
}
.unit-toggle { display: flex; border: 1px solid #DDD; }
.unit-opt {
  background: none;
  border: none;
  padding: 7px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  letter-spacing: 0.5px;
  color: #666;
  cursor: pointer;
  transition: all .2s;
}
.unit-opt.active { background: #000; color: #fff; }
.unit-opt:not(.active):hover { background: #F0F0F0; }

/* 事件列表 */
.events-list {
  border: 1px solid #CCC;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.event-row {
  display: flex;
  align-items: center;
  gap: 14px;
}
.event-round {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.event-round label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  color: #999;
  letter-spacing: 0.5px;
}
.event-num {
  width: 60px;
  border: 1px solid #DDD;
  background: #FAFAFA;
  padding: 8px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.88rem;
  outline: none;
  text-align: center;
}
.event-desc {
  flex: 1;
  border: 1px solid #DDD;
  background: #FAFAFA;
  padding: 12px 14px;
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-size: 0.88rem;
  outline: none;
  color: #000;
}
.event-num:focus, .event-desc:focus { border-color: #FF4500; background: #fff; }
.event-remove {
  background: none;
  border: 1px solid #EEE;
  padding: 8px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #999;
  cursor: pointer;
  transition: all .2s;
  white-space: nowrap;
}
.event-remove:hover { border-color: #FF4500; color: #FF4500; }
.event-add {
  align-self: flex-start;
  background: none;
  border: 1px dashed #CCC;
  padding: 10px 18px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
  cursor: pointer;
  transition: all .2s;
  margin-top: 4px;
}
.event-add:hover:not(:disabled) { border-color: #FF4500; color: #FF4500; }
.event-add:disabled { opacity: 0.4; cursor: not-allowed; }

/* 提交 */
.submit-section { margin-top: 60px; }
.start-btn {
  width: 100%;
  background: #000;
  color: #fff;
  border: 1px solid #000;
  padding: 22px 30px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 1.05rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
}
.start-btn.pulsing { animation: pulse-border 2s infinite; }
.start-btn:hover:not(:disabled) {
  background: #FF4500;
  border-color: #FF4500;
  transform: translateY(-2px);
}
.start-btn:disabled {
  background: #E5E5E5;
  color: #999;
  border-color: #E5E5E5;
  cursor: not-allowed;
}
.btn-arrow { font-size: 1.2rem; }
.seed-error {
  margin-top: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #e11d48;
  letter-spacing: 0.3px;
}

/* 补充资料上传 */
.upload-hint { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #999; }
.upload-area { display: flex; flex-direction: column; gap: 10px; }
.upload-input { display: none; }
.upload-btn { align-self: flex-start; background: none; border: 1px dashed #BBB; color: #666; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; padding: 8px 18px; cursor: pointer; transition: all .2s; }
.upload-btn:hover:not(:disabled) { border-color: #FF4500; color: #FF4500; }
.upload-btn:disabled { opacity: .5; cursor: not-allowed; }
.upload-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.upload-chip { display: inline-flex; align-items: center; gap: 8px; border: 1px solid #E0E0E0; background: #FAFAFA; padding: 5px 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; max-width: 100%; }
.upload-chip b { font-weight: 600; color: #333; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-chip.err { border-color: #fecdd3; background: #fff1f2; }
.chip-status { font-style: normal; color: #999; }
.chip-status.ok { color: #16a34a; }
.upload-chip.err .chip-status { color: #e11d48; }
.chip-remove { font-style: normal; color: #999; cursor: pointer; padding: 0 2px; }
.chip-remove:hover { color: #e11d48; }

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(255,69,0,0.25); }
  70% { box-shadow: 0 0 0 8px rgba(255,69,0,0); }
  100% { box-shadow: 0 0 0 0 rgba(255,69,0,0); }
}

@media (max-width: 768px) {
  .main-content { padding: 40px 20px 80px; }
  .params-row { flex-direction: column; align-items: flex-start; gap: 18px; }
  .param-divider { display: none; }
  .event-row { flex-direction: column; align-items: stretch; }
}
</style>
