import type { Register, SessionMessage } from 'claude-code'
import { applyMasks, dropRepeatedRows, placeholder, selectMasks } from '../lib/policy.ts'
import type { MaskCandidate, MaskCounts } from '../lib/policy.ts'
import { cleanup, loadManifest, logPathOf, settleEntries, spillBatch, spillRootOf, touchActivity } from '../lib/spill.ts'
import type { SpillHost } from '../lib/spill.ts'

/** What `$.clock.after` hands back: `cancel()` before it fires stops it. */
type TimerHandle = { cancel(): unknown }

/**
 * The part of a plugin's `$` the helpers below call beside what the spill functions take; the engine's `$`
 * satisfies it as it is. `session.messages` is declared in the two forms the helpers call: bare for the rows,
 * `{ as: 'api' }` for the Messages API form.
 */
type Host = SpillHost & {
  env: { get(name: string): Promise<string | undefined> }
  clock: { now(): Promise<number>; after(ms: number, fn: () => void): TimerHandle }
  session: {
    id(): Promise<string>
    usage(): Promise<unknown>
    messages(): Promise<unknown>
    messages(args: { as: 'api' }): Promise<unknown>
  }
  command: { run(args: { command: string; args?: string }): Promise<unknown> }
  ui: { log(text: string): unknown }
}

/** The settings `plugin.json` declares under `userConfig`, each defaulting as declared there. */
type Config = {
  enabled: boolean
  idleGuardMinutes: number
  idleMinTokens: number
  keepRecentUserTurns: number
  minMaskChars: number
  minNetReductionPercent: number
  minNetReductionTokens: number
  remaskOnResume: boolean
  spillDir: string
  spillRetentionDays: number
}

type NumberKey =
  | 'idleGuardMinutes'
  | 'idleMinTokens'
  | 'keepRecentUserTurns'
  | 'minMaskChars'
  | 'minNetReductionPercent'
  | 'minNetReductionTokens'
  | 'spillRetentionDays'

/** The range a numeric setting must fall in; `expected` is how a refusal names it. */
type NumberRule = { key: NumberKey; isInteger: boolean; min: number; max: number; expected: string }

/**
 * Everything one activation keeps between events. It lives inside `register`, so a reload (a settings change,
 * a test) starts from a fresh one and nothing carries over at module scope.
 */
type State = {
  config: Config
  /** Why the settings were refused, or null. A refused setting turns the plugin off as `enabled: false` does. */
  configError: string | null
  configErrorReported: boolean
  /** Whether this activation already said that the context size could not be read. */
  usageUnreadableReported: boolean
  /** `enabled` with no setting refused: the switch every timer, command and guidance waits on. */
  active: boolean
  /** Moved on by every main-loop `turn.complete`; a timer or a queued compaction of an older generation does nothing. */
  generation: number
  /**
   * Between a main-loop `turn.start` and its `turn.complete`. The engine can take a queued `/compact` off the queue
   * as the turn ends but before this plugin's `turn.complete` moves the generation on, so a marked compaction
   * checks this too.
   */
  turnUnderWay: boolean
  /** When the main loop last completed a turn, in `$.clock.now()` milliseconds (until then, on a warm resume, the activity its manifest recorded); null while no time was read. */
  lastActivityAt: number | null
  /** The generation an idle compaction was queued for: one generation queues at most one. */
  queuedGeneration: number | null
  /** The pending idle timer and the generation it was armed for; null once it fired or was disarmed. */
  timer: { generation: number; handle: TimerHandle } | null
  /** The spill root once read: a path, null when there is none, undefined before the first read. */
  root: string | null | undefined
}

/** The plugin's own `/compact` arguments: the idle compaction of one generation, or the remask after a resume. */
type Marker = { kind: 'idle'; generation: number; text: string } | { kind: 'resume'; text: string }

/** The fields of `session.compact`'s input a masking reads. */
type CompactEvent = { trigger: string; instructions?: string; messages: readonly SessionMessage[] }

type CompactAnswer = { skip: string } | { messages: SessionMessage[] }

/**
 * One observation, written as a `$.ui.log` line and as a line of `<root>/<sessionId>.log.jsonl`, for each
 * compaction that carries the marker. `counts` is `selectMasks`'s, null when the compaction stopped before the
 * policy ran: `mask` the results the policy found eligible, `recent` those in the protected recent rows, and
 * `error`, `image`, `tool`, `small` and `already` the results kept for that reason. `charsBefore` and
 * `charsAfter` count tool result characters; `spilledBytes` the UTF-8 bytes of the spilled results the masking used.
 */
type Observation = {
  trigger: string
  marker: string
  generation: number
  counts: MaskCounts | null
  charsBefore: number
  charsAfter: number
  spilledBytes: number
  outcome: 'masked' | 'skip' | 'pass' | 'deduped'
  reason: string
}

const DEFAULTS: Config = {
  enabled: false,
  idleGuardMinutes: 61,
  idleMinTokens: 200000,
  keepRecentUserTurns: 6,
  minMaskChars: 1200,
  minNetReductionPercent: 20,
  minNetReductionTokens: 50000,
  remaskOnResume: true,
  spillDir: '',
  spillRetentionDays: 30,
}

const NUMBER_RULES: readonly NumberRule[] = [
  { key: 'idleGuardMinutes', isInteger: false, min: 1, max: Number.POSITIVE_INFINITY, expected: 'a number of at least 1' },
  { key: 'idleMinTokens', isInteger: false, min: 1, max: Number.POSITIVE_INFINITY, expected: 'a number of at least 1' },
  { key: 'keepRecentUserTurns', isInteger: true, min: 1, max: Number.POSITIVE_INFINITY, expected: 'a whole number of at least 1' },
  { key: 'minMaskChars', isInteger: true, min: 1, max: Number.POSITIVE_INFINITY, expected: 'a whole number of at least 1' },
  { key: 'minNetReductionPercent', isInteger: false, min: 0, max: 100, expected: 'a number from 0 to 100' },
  { key: 'minNetReductionTokens', isInteger: false, min: 0, max: Number.POSITIVE_INFINITY, expected: 'a number of at least 0' },
  { key: 'spillRetentionDays', isInteger: false, min: 1, max: Number.POSITIVE_INFINITY, expected: 'a number of at least 1' },
]

/** `/compact` arguments that begin with this are the plugin's own; the engine hands them on as `instructions`. */
const MARKER = 'fz-compact:'
const IDLE_MARKER = `${MARKER}idle:`
const RESUME_MARKER = `${MARKER}resume`
const OFF_SKIP = 'fz-compact: off (enabled is false or a setting is invalid)'
const SPILL_ALLOW_REASON = 'fz-compact spill file'
/** The observation log keeps its last this-many lines. */
const LOG_KEEP_LINES = 200
const MINUTE_MS = 60_000
/** The characters taken for one token when a saving is weighed against `minNetReductionTokens` and when a resume estimates the context's size: an estimate, no tokenizer. */
const CHARS_PER_TOKEN = 4

/** Appended after the person's own focus, if any, to every compaction the engine summarizes while the plugin is on. */
const GUIDANCE = [
  'fz-compact guidance (appended after any user focus, which takes priority):',
  "- Keep verbatim: the user's goal and every explicit constraint, approval or correction.",
  '- Keep: decisions with reasons, rejected alternatives, failed attempts, verification commands with outcomes, error diagnoses, open questions, the next action.',
  '- Keep exact anchors: file paths with line numbers, symbols, ticket IDs, artifact and checkpoint paths.',
  '- Summarize bulky tool output by what it established; keep any result the next action depends on.',
].join('\n')

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/**
 * A `turn.start` input's `agentId`: a string inside a subagent's or a fork's loop, undefined on the main loop.
 * Read through `unknown` since that input's type is not pinned down beside this file; `turn.complete` and
 * `session.compact` read `e.agentId` as typed.
 */
function agentIdOf(e: unknown): string | undefined {
  return isRecord(e) && typeof e.agentId === 'string' ? e.agentId : undefined
}

/**
 * The settings as `register` received them, a missing one at its default, each checked against its range;
 * `spillDir` must be empty or name an absolute folder other than `/` alone, as `spillRootOf` takes one.
 * Every refusal is named in `error`; the plugin then stays off whatever `enabled` says.
 */
function readConfig(options: Readonly<Record<string, unknown>>): { config: Config; error: string | null } {
  const config: Config = { ...DEFAULTS }
  const problems: string[] = []
  for (const key of ['enabled', 'remaskOnResume'] as const) {
    const value = options[key] ?? DEFAULTS[key]
    if (typeof value === 'boolean') config[key] = value
    else problems.push(`${key} must be true or false`)
  }
  for (const rule of NUMBER_RULES) {
    const value = options[rule.key] ?? DEFAULTS[rule.key]
    if (typeof value === 'number' && Number.isFinite(value) && value >= rule.min && value <= rule.max && (!rule.isInteger || Number.isInteger(value))) config[rule.key] = value
    else problems.push(`${rule.key} must be ${rule.expected}`)
  }
  const spillDir = options['spillDir'] ?? DEFAULTS.spillDir
  if (typeof spillDir !== 'string') problems.push('spillDir must be text')
  else if (spillDir !== '' && spillRootOf(undefined, spillDir) === null) problems.push('spillDir must be an absolute folder other than / alone, or empty')
  else config.spillDir = spillDir
  return { config, error: problems.length === 0 ? null : `invalid settings: ${problems.join('; ')}` }
}

/** The marker in `instructions`, trailing space dropped, or null for text that only begins like one. */
function markerOf(instructions: string): Marker | null {
  const text = instructions.trimEnd()
  if (text === RESUME_MARKER) return { kind: 'resume', text }
  if (!text.startsWith(IDLE_MARKER)) return null
  const digits = text.slice(IDLE_MARKER.length)
  if (!/^[0-9]+$/.test(digits)) return null
  const generation = Number(digits)
  return Number.isSafeInteger(generation) ? { kind: 'idle', generation, text } : null
}

/** Every message's own text, in characters. */
function messageChars(messages: readonly SessionMessage[]): number {
  let total = 0
  for (const message of messages) total += message.text.length
  return total
}

/** Every tool result's text, in characters. */
function resultChars(messages: readonly SessionMessage[]): number {
  let total = 0
  for (const message of messages) for (const result of message.toolResults ?? []) total += result.text.length
  return total
}

/** Every tool call's arguments, each `input` counted as the length of its JSON text; one that cannot be written as JSON counts 0. */
function toolInputChars(messages: readonly SessionMessage[]): number {
  let total = 0
  for (const message of messages) {
    for (const use of message.toolUses ?? []) {
      try {
        const json = JSON.stringify(use.input)
        if (typeof json === 'string') total += json.length
      } catch {
        // an input JSON cannot hold (a cycle, a BigInt) counts 0
      }
    }
  }
  return total
}

/**
 * The conversation's characters: what `minNetReductionPercent` weighs a saving against, and what a resume estimates
 * the context's size from when the session reports none. It counts every message's own text (`messageChars`), every
 * tool call's arguments as JSON (`toolInputChars`) and every tool result's text (`resultChars`).
 */
function conversationChars(messages: readonly SessionMessage[]): number {
  return messageChars(messages) + toolInputChars(messages) + resultChars(messages)
}

/** `resultChars` of a compaction's answer, or `fallback` for a skip. */
function resultCharsOf(result: unknown, fallback: number): number {
  return isRecord(result) && Array.isArray(result.messages) ? resultChars(result.messages) : fallback
}

/** UTF-8 bytes, counted as `lib/spill.ts` counts them for its caps (its own copy is not exported). */
function utf8Length(text: string): number {
  return new TextEncoder().encode(text).length
}

/**
 * Where `spillBatch` puts a result, `<root>/<sessionId>/<tool_use_id>.txt`. It sizes the placeholders before anything
 * is written (the placeholder that goes in takes the path `spillBatch` answers), and `isSpillFile` matches a Read
 * against it. It must spell the path as `spillPathOf` in `lib/spill.ts` does (not exported): a change there leaves
 * the masking right, but puts this estimate off and has `tool.check` allow no spill file, so the engine's verdict
 * stands for every Read of one.
 */
function expectedSpillPath(root: string, sessionId: string, toolUseId: string): string {
  return `${root}/${sessionId}/${toolUseId}.txt`
}

/**
 * Why masking these candidates is not worth a compaction, or null when it is. `before` is the rows'
 * `conversationChars` (message text, tool-call arguments and tool results); `saved` each candidate's characters
 * less its placeholder's. Both thresholds must hold: `minNetReductionPercent` of `before`, and
 * `minNetReductionTokens` at `CHARS_PER_TOKEN` characters a token.
 */
function shortfallOf(messages: readonly SessionMessage[], candidates: readonly MaskCandidate[], root: string, sessionId: string, config: Config): string | null {
  const before = conversationChars(messages)
  let saved = 0
  for (const candidate of candidates) {
    saved += candidate.chars - placeholder(candidate.tool, candidate.chars, expectedSpillPath(root, sessionId, candidate.tool_use_id)).length
  }
  if (saved >= (before * config.minNetReductionPercent) / 100 && saved / CHARS_PER_TOKEN >= config.minNetReductionTokens) return null
  return `masking would save ${saved} of ${before} chars, under ${config.minNetReductionPercent}% or ${config.minNetReductionTokens} tokens`
}

/** The indices of the rows of `masked` that are not the very row of `rows` at the same index: the rows `applyMasks` replaced. */
function changedRowsOf(rows: readonly SessionMessage[], masked: readonly SessionMessage[]): Set<number> {
  const changed = new Set<number>()
  for (const [index, message] of masked.entries()) if (message !== rows[index]) changed.add(index)
  return changed
}

/** The tool_use_ids of every result in the rows of `messages` at `indices`. */
function carriedIdsOf(messages: readonly SessionMessage[], indices: ReadonlySet<number>): Set<string> {
  const ids = new Set<string>()
  for (const index of indices) for (const result of messages[index]?.toolResults ?? []) ids.add(result.tool_use_id)
  return ids
}

/** The context window's token count as `$.session.usage()` reports it (`context.tokens`), or undefined without one. */
function contextTokensOf(usage: unknown): number | undefined {
  if (!isRecord(usage) || !isRecord(usage.context)) return undefined
  const tokens = usage.context.tokens
  return typeof tokens === 'number' && Number.isFinite(tokens) ? tokens : undefined
}

/** An absolute path's components (`/a/b` gives `['a', 'b']`), or null for a path that is not absolute. */
function partsOf(path: string): string[] | null {
  if (path.charAt(0) !== '/') return null
  return path.split('/').filter((part) => part !== '')
}

/** Disarms the pending idle timer: its `cancel()` is asked, and a callback that fires anyway finds it disarmed. */
function cancelTimer(state: State): void {
  const timer = state.timer
  state.timer = null
  if (timer === null) return
  try {
    void Promise.resolve(timer.handle.cancel()).catch(() => undefined)
  } catch {
    // a timer that cannot be cancelled finds itself disarmed when it fires
  }
}

/** Whether the timer armed for `generation` is still the pending one, that generation current and not yet queued. */
function isArmed(state: State, generation: number): boolean {
  return state.timer !== null && state.timer.generation === generation && state.generation === generation && state.queuedGeneration !== generation
}

function staleReasonOf(generation: number, state: State): string {
  return `generation ${generation} is stale; the session is at ${state.generation}`
}

function lineOf(record: Observation): string {
  return `fz-compact ${record.outcome}: ${record.reason} (${record.trigger} ${record.marker}, generation ${record.generation}, tool results ${record.charsBefore} -> ${record.charsAfter} chars, ${record.spilledBytes} bytes spilled)`
}

/** A line through `$.ui.log`; one that cannot be shown is dropped. */
function say($: Host, text: string): void {
  try {
    void Promise.resolve($.ui.log(text)).catch(() => undefined)
  } catch {
    // a line the host refuses is dropped
  }
}

/** Says once per activation why the settings turned the plugin off; nothing when they did not. */
function reportConfigError($: Host, state: State): void {
  if (state.configError === null || state.configErrorReported) return
  state.configErrorReported = true
  say($, `fz-compact is off: ${state.configError}`)
}

/** Says once per activation that idle masking waits on a context size it cannot read. */
function reportUsageUnreadable($: Host, state: State): void {
  if (state.usageUnreadableReported) return
  state.usageUnreadableReported = true
  say($, 'fz-compact: idle masking not queued: the context token count (usage context.tokens) could not be read')
}

async function nowOf($: Host): Promise<number | null> {
  try {
    const now = await $.clock.now()
    return Number.isFinite(now) ? now : null
  } catch {
    return null
  }
}

async function isBackground($: Host): Promise<boolean> {
  try {
    return (await $.env.get('CLAUDE_CODE_SESSION_KIND')) === 'bg'
  } catch {
    return false
  }
}

async function sessionIdOf($: Host): Promise<string | null> {
  try {
    const id = await $.session.id()
    return typeof id === 'string' && id !== '' ? id : null
  } catch {
    return null
  }
}

async function homeOf($: Host): Promise<string | undefined> {
  try {
    return await $.env.get('HOME')
  } catch {
    return undefined
  }
}

/** The spill root (`spillDir`, else under HOME), read once per activation; null when there is none. */
async function rootOf($: Host, state: State): Promise<string | null> {
  if (state.root !== undefined) return state.root
  const home = state.config.spillDir === '' ? await homeOf($) : undefined
  state.root = spillRootOf(home, state.config.spillDir)
  return state.root
}

/**
 * The idle time after which a background session's old tool results may be masked: `minutes` (the
 * `idleGuardMinutes` setting) in milliseconds, or `FZ_COMPACT_TEST_IDLE_MS` when that is a positive whole
 * number of milliseconds. The idle timer, the check a queued compaction makes when it runs, and the resume
 * check all take it from here, so they never disagree.
 */
async function idleThresholdMs($: Host, minutes: number): Promise<number> {
  let raw: string | undefined
  try {
    raw = await $.env.get('FZ_COMPACT_TEST_IDLE_MS')
  } catch {
    raw = undefined
  }
  if (raw !== undefined && /^[1-9][0-9]*$/.test(raw)) {
    const ms = Number(raw)
    if (Number.isSafeInteger(ms)) return ms
  }
  return minutes * MINUTE_MS
}

/**
 * After a main-loop turn: a new generation, the pending idle timer disarmed, the activity time now and recorded
 * in the session's manifest without waiting; in a background session the idle timer armed for the new generation.
 */
async function afterMainTurn($: Host, state: State): Promise<void> {
  state.generation += 1
  const generation = state.generation
  cancelTimer(state)
  const now = await nowOf($)
  if (state.generation !== generation) return
  state.lastActivityAt = now
  if (now === null) return
  const root = await rootOf($, state)
  const sessionId = await sessionIdOf($)
  if (root !== null && sessionId !== null) void touchActivity($, root, sessionId, now)
  if (!(await isBackground($))) return
  const thresholdMs = await idleThresholdMs($, state.config.idleGuardMinutes)
  if (state.generation !== generation) return
  armIdleTimer($, state, generation, thresholdMs)
}

/**
 * Arms the idle timer for `generation`, due in `delayMs`, in place of any pending one; when it fires, `fireIdle`
 * decides. A clock that refuses the timer leaves none armed.
 */
function armIdleTimer($: Host, state: State, generation: number, delayMs: number): void {
  cancelTimer(state)
  try {
    const handle = $.clock.after(delayMs, () => {
      void fireIdle($, state, generation)
    })
    state.timer = { generation, handle }
  } catch {
    state.timer = null
  }
}

/**
 * The idle timer's end: queues the idle compaction, once per generation, while the timer is still armed for the
 * current generation and the context holds at least `idleMinTokens`. A context size that cannot be read queues
 * nothing and says so once.
 */
async function fireIdle($: Host, state: State, generation: number): Promise<void> {
  if (!isArmed(state, generation)) return
  let usage: unknown
  try {
    usage = await $.session.usage()
  } catch {
    usage = undefined
  }
  if (!isArmed(state, generation)) return
  state.timer = null
  const tokens = contextTokensOf(usage)
  if (tokens === undefined) {
    reportUsageUnreadable($, state)
    return
  }
  if (tokens < state.config.idleMinTokens) return
  state.queuedGeneration = generation
  queueCompact($, `${IDLE_MARKER}${generation}`)
}

/**
 * Queues `/compact <args>` to run once the session is idle, without waiting for it: a hook the turn waits on
 * cannot. A refusal leaves a line and the conversation as it is.
 */
function queueCompact($: Host, args: string): void {
  const refused = `fz-compact: /compact ${args} could not be queued`
  try {
    void $.command.run({ command: 'compact', args }).catch(() => say($, refused))
  } catch {
    say($, refused)
  }
}

/** Whether the main transcript holds any row: a resumed session, not a fresh one. A failed read is a no. */
async function hasRows($: Host): Promise<boolean> {
  try {
    const rows = await $.session.messages()
    return Array.isArray(rows) && rows.length > 0
  } catch {
    return false
  }
}

/**
 * On a resumed background session: queues the remask when the manifest names spilled results, or once its recorded
 * last activity is `idleThresholdMs` old whether or not it does. While that activity is younger and no main turn has
 * run in this activation (none completed, none under way), also takes it for the last activity and arms the idle
 * timer of generation 0 for the rest of the threshold, so a session nobody turns again still masks once idle. A
 * `lastActivityAt` of 0 is no record, never a long idle: it arms no timer.
 *
 * - Note: `session.start` also fires when this plugin is loaded again in a running session (a reload after a
 *   settings change, a worker respawn, an enable), with a fresh activation that saw none of its turns. The
 *   recorded activity is what tells a session someone is using from one gone cold.
 */
async function queueResume($: Host, state: State): Promise<void> {
  const root = await rootOf($, state)
  const sessionId = await sessionIdOf($)
  if (root === null || sessionId === null) return
  const manifest = await loadManifest($, root, sessionId)
  if (manifest === null) return
  const lastActivityAt = manifest.lastActivityAt
  const now = lastActivityAt > 0 ? await nowOf($) : null
  if (now === null) {
    if (manifest.entries.length > 0) queueCompact($, RESUME_MARKER)
    return
  }
  const thresholdMs = await idleThresholdMs($, state.config.idleGuardMinutes)
  const idleMs = now - lastActivityAt
  const isCold = idleMs >= thresholdMs
  if (isCold || manifest.entries.length > 0) queueCompact($, RESUME_MARKER)
  if (isCold || state.generation !== 0 || state.turnUnderWay) return
  state.lastActivityAt = lastActivityAt
  armIdleTimer($, state, state.generation, thresholdMs - idleMs)
}

/**
 * Removes spill files past their keep; nothing waits on it, and what stays is looked at again next start. It
 * runs whenever the settings are valid, enabled or not, so what was spilled before the plugin was turned off
 * still goes once past `spillRetentionDays`. This session's own files are passed over (`cleanup`'s
 * `liveSessionId`), since the remask this start may queue rewrites them; the start of another session looks at
 * them. With no session id read, every session is looked at, as no remask runs then either.
 */
async function sweep($: Host, state: State): Promise<void> {
  const root = await rootOf($, state)
  const now = await nowOf($)
  if (root === null || now === null) return
  const sessionId = await sessionIdOf($)
  try {
    await cleanup($, root, now, state.config.spillRetentionDays, sessionId ?? undefined)
  } catch {
    // what is not removed now is looked at again on the next session start
  }
}

/**
 * The tool_use_ids whose tool_result carries an image block, read from the Messages API form since the rows
 * show no images; null when that form cannot be read.
 */
async function imageIdsOf($: Host): Promise<Set<string> | null> {
  let rows: unknown
  try {
    rows = await $.session.messages({ as: 'api' })
  } catch {
    return null
  }
  if (!Array.isArray(rows)) return null
  const ids = new Set<string>()
  for (const row of rows) {
    const content = isRecord(row) ? row.content : undefined
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (!isRecord(block) || block.type !== 'tool_result' || typeof block.tool_use_id !== 'string') continue
      if (Array.isArray(block.content) && block.content.some((part: unknown) => isRecord(part) && part.type === 'image')) ids.add(block.tool_use_id)
    }
  }
  return ids
}

/**
 * The tool_use_ids the session's manifest already names (`named`), and those of them it marks confirmed (`confirmed`):
 * results an earlier compaction handed back as placeholders. Both are empty without a readable manifest.
 */
async function manifestIdsOf($: Host, root: string, sessionId: string): Promise<{ named: Set<string>; confirmed: Set<string> }> {
  const entries = (await loadManifest($, root, sessionId))?.entries ?? []
  return {
    named: new Set(entries.map((entry) => entry.tool_use_id)),
    confirmed: new Set(entries.filter((entry) => entry.confirmed).map((entry) => entry.tool_use_id)),
  }
}

/** Whether nothing is at `path`; a failed question counts as something there. */
async function isAbsent($: Host, path: string): Promise<boolean> {
  try {
    return !(await $.fs.exists(path))
  } catch {
    return false
  }
}

/** The log's text, '' when there is none yet, or null when one is there but cannot be read now. */
async function previousLogOf($: Host, path: string): Promise<string | null> {
  try {
    return await $.fs.read(path)
  } catch {
    return (await isAbsent($, path)) ? '' : null
  }
}

/**
 * Leaves one observation: a `$.ui.log` line, and a line appended to the session's log (read, appended, its last
 * `LOG_KEEP_LINES` lines written back). A log that is there but cannot be read is left as it is.
 */
async function observe($: Host, state: State, record: Observation): Promise<void> {
  say($, lineOf(record))
  const root = await rootOf($, state)
  const sessionId = await sessionIdOf($)
  if (root === null || sessionId === null) return
  const path = logPathOf(root, sessionId)
  const previous = await previousLogOf($, path)
  if (previous === null) return
  const lines = previous.split('\n').filter((entry) => entry !== '')
  lines.push(JSON.stringify({ at: await nowOf($), sessionId, ...record }))
  try {
    await $.fs.write(path, `${lines.slice(-LOG_KEEP_LINES).join('\n')}\n`)
  } catch {
    // the line is dropped: no compaction waits on its log
  }
}

async function skipWith($: Host, state: State, record: Observation, reason: string): Promise<CompactAnswer> {
  await observe($, state, { ...record, outcome: 'skip', reason })
  return { skip: `fz-compact: ${reason}` }
}

/**
 * The answer of a marked compaction left with nothing to mask: the skip for `reason`, or, when `dropped` repeated
 * rows were taken out, `rows` handed back as the compaction, so a resume after an earlier masking still loses them.
 */
async function skipUnlessDeduped($: Host, state: State, record: Observation, rows: SessionMessage[], dropped: number, reason: string): Promise<CompactAnswer> {
  if (dropped === 0) return skipWith($, state, record, reason)
  await observe($, state, { ...record, charsAfter: resultChars(rows), outcome: 'deduped', reason: `dropped ${dropped} repeated rows; ${reason}` })
  return { messages: rows }
}

/**
 * Why a marked compaction may not run now, or null. Neither kind runs while a main-loop turn is under way. An idle
 * one needs its generation still current and `idleThresholdMs` passed since the last activity, read again here
 * since the session may have woken while it waited in the queue; a resume one needs `remaskOnResume`, a background session, and no main turn completed in
 * this process yet: once one has, its request already rewrote the cache with the originals, and masking now would
 * only rewrite it again.
 */
async function refusalOf($: Host, state: State, marker: Marker): Promise<string | null> {
  if (state.turnUnderWay) return 'a main-loop turn started while this compaction waited in the queue, so the cache is in use again'
  if (marker.kind === 'resume') {
    if (!state.config.remaskOnResume) return 'masking on resume is off (remaskOnResume)'
    if (state.generation !== 0) return `a main turn already ran in this process (generation ${state.generation}), so the cache holds the originals again`
    return (await isBackground($)) ? null : 'masking on resume runs in background sessions only'
  }
  if (marker.generation !== state.generation) return staleReasonOf(marker.generation, state)
  const lastActivityAt = state.lastActivityAt
  const now = await nowOf($)
  const thresholdMs = await idleThresholdMs($, state.config.idleGuardMinutes)
  if (marker.generation !== state.generation) return staleReasonOf(marker.generation, state)
  if (lastActivityAt === null || now === null) return 'no activity time to measure the idle time from'
  if (now - lastActivityAt >= thresholdMs) return null
  return `the session was active ${now - lastActivityAt} ms ago, under the ${thresholdMs} ms idle threshold`
}

/**
 * Records in the session's manifest, and waits for it, what became of the results `spilled` names: those the rows
 * handed back carry as a placeholder (`carried`) are confirmed, so a later resume masks them again without the saving
 * check; those the manifest did not name before the spill (`named`) and the rows do not carry are taken out, their
 * spill files left for cleanup to reclaim. Only a confirmed result skips that check, so a manifest that cannot be
 * rewritten costs a line and leaves those results to be weighed again on a resume.
 */
async function settleSpilled($: Host, root: string, sessionId: string, spilled: ReadonlyMap<string, string>, named: ReadonlySet<string>, carried: ReadonlySet<string>): Promise<void> {
  const ids = [...spilled.keys()]
  const confirm = ids.filter((id) => carried.has(id))
  const drop = ids.filter((id) => !named.has(id) && !carried.has(id))
  if (confirm.length === 0 && drop.length === 0) return
  if (!(await settleEntries($, root, sessionId, confirm, drop))) {
    say($, `fz-compact: the manifest could not be updated for ${confirm.length + drop.length} spilled results, so a resume may weigh their saving again`)
  }
}

/**
 * Why a resume leaves the results its manifest has not confirmed unmasked for the context's size, or null when the
 * context holds at least `idleMinTokens`, as `fireIdle` asks before it queues an idle compaction. The size is
 * `context.tokens` of `$.session.usage()` (a failed call counts as none), or, when the session reports none, the
 * rows' `conversationChars` at `CHARS_PER_TOKEN` characters a token.
 *
 * - Note: `context.tokens` is absent until the live window's first response (it is the last response's input side),
 *   and a resume's remask runs only before any main turn completes in this process (`refusalOf`), so a cold resume
 *   normally takes the estimate; a reported size comes mostly when the plugin is loaded again in a running session.
 *   The estimate leaves out what the rows do not carry, such as the system prompt and attachments, so it can fall
 *   under `idleMinTokens` where `fireIdle` would not.
 */
async function contextShortfallOf($: Host, rows: readonly SessionMessage[], config: Config): Promise<string | null> {
  let usage: unknown
  try {
    usage = await $.session.usage()
  } catch {
    usage = undefined
  }
  const reported = contextTokensOf(usage)
  const chars = reported === undefined ? conversationChars(rows) : 0
  const tokens = reported ?? chars / CHARS_PER_TOKEN
  if (tokens >= config.idleMinTokens) return null
  const size = reported === undefined ? `about ${Math.floor(tokens)} tokens (${chars} chars; no context size was reported)` : `${reported} tokens`
  return `the context holds ${size}, under idleMinTokens ${config.idleMinTokens}`
}

/**
 * A compaction carrying the plugin's marker: checked again now that it runs, then the eligible tool results
 * spilled and replaced by placeholders, with no model call. On a resume, results the manifest marks confirmed (an
 * earlier compaction handed them back as placeholders) are masked again without the saving check (they passed it
 * when first masked, and the same placeholders rebuild the prefix the session had); the others, named by the
 * manifest or not, join only when the context holds at least `idleMinTokens` (`contextShortfallOf`) and they pass
 * the saving check on their own. A row is masked only whole, so a result the saving check weighs counts toward it
 * only once it and every other result of its row are spilled; when only some of those results count (on a resume or
 * an idle compaction alike), they are checked again by themselves and masked only when they pass. Before the answer
 * goes back, the manifest is told what became of the results this compaction spilled (`settleSpilled`): those the
 * rows handed back carry are confirmed, and those it did not name before that the rows do not carry are taken out;
 * when that rewrite fails, those it would have confirmed or taken out stay unconfirmed, so a resume weighs them
 * again. Once the check at run time
 * passes and the spill folder, session id and image blocks are read, and before any result is picked, rows that
 * repeat the row kept before them (`dropRepeatedRows`, as a resume hands them) are dropped; when some were, a
 * compaction left with nothing to mask hands the rest back in place of a skip. A skip leaves the conversation as
 * it is; so does every row whose results were not all spilled.
 */
async function maskCompaction($: Host, state: State, e: CompactEvent, marker: Marker): Promise<CompactAnswer> {
  const charsBefore = resultChars(e.messages)
  const record: Observation = {
    trigger: e.trigger,
    marker: marker.text,
    generation: state.generation,
    counts: null,
    charsBefore,
    charsAfter: charsBefore,
    spilledBytes: 0,
    outcome: 'skip',
    reason: '',
  }
  const refusal = await refusalOf($, state, marker)
  if (refusal !== null) return skipWith($, state, record, refusal)
  const root = await rootOf($, state)
  if (root === null) return skipWith($, state, record, 'no usable spill folder (spillDir is empty and HOME could not be read)')
  const sessionId = await sessionIdOf($)
  if (sessionId === null) return skipWith($, state, record, 'the session id could not be read')
  const imageIds = await imageIdsOf($)
  if (imageIds === null) return skipWith($, state, record, 'the image blocks could not be read')
  const { messages: rows, dropped } = dropRepeatedRows(e.messages)
  const { candidates, counts } = selectMasks(rows, {
    keepRecentUserTurns: state.config.keepRecentUserTurns,
    minMaskChars: state.config.minMaskChars,
    imageIds,
  })
  const measured: Observation = { ...record, counts }
  if (candidates.length === 0) return skipUnlessDeduped($, state, measured, rows, dropped, 'no tool result to mask')
  const prior = await manifestIdsOf($, root, sessionId)
  const known = marker.kind === 'resume' ? prior.confirmed : new Set<string>()
  const fresh = candidates.filter((candidate) => !known.has(candidate.tool_use_id))
  const undersized = marker.kind === 'resume' && fresh.length > 0 ? await contextShortfallOf($, rows, state.config) : null
  const shortfall = fresh.length === 0 ? null : (undersized ?? shortfallOf(rows, fresh, root, sessionId, state.config))
  const chosen = shortfall === null ? candidates : candidates.filter((candidate) => known.has(candidate.tool_use_id))
  if (chosen.length === 0) return skipUnlessDeduped($, state, measured, rows, dropped, shortfall ?? 'no tool result to mask')
  const items = chosen.map((candidate) => ({ tool_use_id: candidate.tool_use_id, tool: candidate.tool, text: candidate.text }))
  const spilled = await spillBatch($, root, sessionId, state.generation, items)
  const replacements = new Map<string, string>()
  for (const candidate of chosen) {
    const path = spilled.get(candidate.tool_use_id)
    if (path !== undefined) replacements.set(candidate.tool_use_id, placeholder(candidate.tool, candidate.chars, path))
  }
  const trial = applyMasks(rows, replacements)
  const trialRows = changedRowsOf(rows, trial)
  const landed = fresh.filter((candidate) => replacements.has(candidate.tool_use_id) && trialRows.has(candidate.messageIndex))
  const recheck = shortfall === null && landed.length > 0 && landed.length < fresh.length ? shortfallOf(rows, landed, root, sessionId, state.config) : null
  const spillShortfall = recheck === null ? null : `after spill failures, ${recheck}`
  if (spillShortfall !== null) {
    for (const candidate of fresh) replacements.delete(candidate.tool_use_id)
  }
  const messages = spillShortfall === null ? trial : applyMasks(rows, replacements)
  const changed = changedRowsOf(rows, messages)
  const carried = carriedIdsOf(messages, changed)
  const maskedRows = changed.size
  let spilledBytes = 0
  for (const candidate of chosen) if (carried.has(candidate.tool_use_id)) spilledBytes += utf8Length(candidate.text)
  await settleSpilled($, root, sessionId, spilled, prior.named, carried)
  const unmasked = spilled.size === 0 ? 'no result could be spilled, so every original is kept' : 'no row had all its results spilled, so every original is kept'
  if (maskedRows === 0) return skipUnlessDeduped($, state, { ...measured, spilledBytes }, messages, dropped, spillShortfall ?? unmasked)
  const repeats = dropped === 0 ? '' : `; dropped ${dropped} repeated rows`
  const stay = shortfall ?? spillShortfall
  const rest = stay === null ? '' : `; results not masked before stay (${stay})`
  await observe($, state, { ...measured, charsAfter: resultChars(messages), spilledBytes, outcome: 'masked', reason: `masked ${maskedRows} rows${repeats}${rest}` })
  return { messages }
}

async function realPathOf($: Host, path: string): Promise<string | null> {
  try {
    const stat = await $.fs.stat(path, { resolve: true })
    return typeof stat.realPath === 'string' && stat.realPath !== '' ? stat.realPath : null
  } catch {
    return null
  }
}

/**
 * Whether a Read's `file_path` is a spill file a manifest names. The path and the spill root are both resolved with
 * `$.fs.stat(.., { resolve: true })` and compared component by component. The component right after the root names
 * the session, and the target must then be, component for component, the path `expectedSpillPath` spells under the
 * resolved root for that session and a `tool_use_id` its manifest names, confirmed or not (a placeholder of an
 * unconfirmed entry may be in the rows). A path or root that does not resolve, a link out of the root, a root that
 * resolves to `/`, a sibling that only shares the root's spelling (`spill-other`), any other path under the root,
 * and a manifest that cannot be read now are not.
 */
async function isSpillFile($: Host, state: State, input: unknown): Promise<boolean> {
  const filePath = isRecord(input) && typeof input.file_path === 'string' ? input.file_path : ''
  if (filePath === '') return false
  const root = await rootOf($, state)
  if (root === null) return false
  const target = await realPathOf($, filePath)
  const base = await realPathOf($, root)
  const targetParts = target === null ? null : partsOf(target)
  const baseParts = base === null ? null : partsOf(base)
  if (targetParts === null || baseParts === null || baseParts.length === 0) return false
  if (targetParts.length <= baseParts.length || !baseParts.every((part, index) => targetParts[index] === part)) return false
  const sessionId = targetParts[baseParts.length] ?? ''
  const manifest = await loadManifest($, root, sessionId)
  if (manifest === null) return false
  const resolvedRoot = `/${baseParts.join('/')}`
  const wanted = targetParts.join('/')
  return manifest.entries.some((entry) => partsOf(expectedSpillPath(resolvedRoot, sessionId, entry.tool_use_id))?.join('/') === wanted)
}

export const register: Register = (on, options) => {
  const { config, error } = readConfig(options ?? {})
  const state: State = {
    config,
    configError: error,
    configErrorReported: false,
    usageUnreadableReported: false,
    active: config.enabled && error === null,
    generation: 0,
    turnUnderWay: false,
    lastActivityAt: null,
    queuedGeneration: null,
    timer: null,
    root: undefined,
  }

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    reportConfigError($, state)
    if (state.active && state.config.remaskOnResume && (await isBackground($)) && (await hasRows($))) await queueResume($, state)
    if (state.configError === null) void sweep($, state)
    return started
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined) return result
    reportConfigError($, state)
    // Cleared with no await before afterMainTurn moves the generation on, so no compaction runs between the two.
    state.turnUnderWay = false
    if (state.active) await afterMainTurn($, state)
    return result
  })

  on('session.compact', async ($, e, next) => {
    if (e.agentId !== undefined || e.trigger === 'precompute') return next(e)
    reportConfigError($, state)
    const instructions = e.instructions ?? ''
    const isMarked = e.trigger === 'manual' && instructions.startsWith(MARKER)
    if (isMarked && !state.active) return { skip: OFF_SKIP }
    const marker = isMarked ? markerOf(instructions) : null
    if (marker !== null) return maskCompaction($, state, e, marker)
    if (!state.active) return next(e)
    const guided = { ...e, instructions: (e.instructions ? `${e.instructions}\n\n` : '') + GUIDANCE }
    if (!isMarked) return next(guided)
    const result = await next(guided)
    const charsBefore = resultChars(e.messages)
    await observe($, state, {
      trigger: e.trigger,
      marker: instructions.trimEnd(),
      generation: state.generation,
      counts: null,
      charsBefore,
      charsAfter: resultCharsOf(result, charsBefore),
      spilledBytes: 0,
      outcome: 'pass',
      reason: 'unknown fz-compact marker, so the engine summarized with the guidance',
    })
    return result
  })

  // A Read of a spill file a manifest names (`isSpillFile`) is allowed over the engine's ask or deny, unless a settings
  // rule decided it (`rule`): a rule the person wrote stands. Any other path under the spill root keeps the engine's
  // verdict. The allow does not wait on `enabled`: a session masked before the plugin was turned off still holds
  // placeholders that point at its spill files.
  on('tool.check', { tool: 'Read' }, async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision !== 'allow' && verdict.rule !== undefined) return verdict
    return (await isSpillFile($, state, e.input)) ? { decision: 'allow' as const, reason: SPILL_ALLOW_REASON } : verdict
  })

  // Disarms the pending idle timer, so a turn under way when it would fire queues nothing, and marks the turn under
  // way, so a /compact queued before the prompt and run as its turn ends is refused. The plugin's own /compact
  // raises no turn.start. The generation still moves only on `turn.complete`.
  on('turn.start', ($, e, next) => {
    if (agentIdOf(e) === undefined) {
      cancelTimer(state)
      state.turnUnderWay = true
    }
    return next(e)
  })
}
