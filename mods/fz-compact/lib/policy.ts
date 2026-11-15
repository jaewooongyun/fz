import type { SessionMessage } from 'claude-code'

type ToolResult = NonNullable<SessionMessage['toolResults']>[number]

/** The tools whose results may be masked; a result of any other tool is kept. A Set: test membership with `has`, not `includes`. */
export const ALLOWED_TOOLS: ReadonlySet<string> = new Set(['Read', 'Grep', 'Glob', 'Bash'])

/** How every placeholder begins: a result whose text begins with it is not masked again. */
export const MARK_PREFIX = '[fz-compact'

/**
 * How a user row the engine writes, not the person, begins: `$.session.messages()` gives a row no origin, so its
 * text, after leading whitespace, is the only sign. `<task-notification>` is a background task's completion delivered
 * as a user message. `<local-command-caveat>`, `<local-command-stdout>` and `<local-command-stderr>` are the output of
 * a local command such as `/login`, not a prompt to the model. `Base directory for this skill:` is the skill body the
 * engine expands after a slash command; the slash command row (`<command-message>` / `<command-name>`) is the human
 * prompt, so counting both would count one prompt twice.
 */
const ENGINE_ROW_PREFIXES: readonly string[] = [
  '<task-notification>',
  '<local-command-caveat>',
  '<local-command-stdout>',
  '<local-command-stderr>',
  'Base directory for this skill:',
]

/**
 * The thresholds `selectMasks` applies, taken as given: range checks belong to the caller.
 * A `keepRecentUserTurns` of 0 or below keeps no row as recent and a `minMaskChars` of 0 or below
 * keeps no result as small, so both mask more; NaN in either masks nothing.
 */
export type MaskOptions = {
  /** Results at or after the oldest of the last this-many human prompts are kept. */
  keepRecentUserTurns: number
  /** A result shorter than this many characters is kept. */
  minMaskChars: number
  /** The tool_use_ids whose results carry an image; those results are kept. */
  imageIds: ReadonlySet<string>
}

export type MaskCandidate = {
  messageIndex: number
  tool_use_id: string
  tool: string
  chars: number
  text: string
}

/**
 * How many tool results each verdict took. Every result is counted under exactly one key, so the
 * keys sum to the number of tool results. A kept key counts the results kept for that reason, not
 * the results that have it: a would-be mask in a mixed row is counted under that row's first kept
 * reason, so a row of one error and one eligible result counts `error` 2.
 */
export type MaskCounts = {
  mask: number
  recent: number
  error: number
  image: number
  tool: number
  small: number
  already: number
}

export type MaskSelection = {
  candidates: MaskCandidate[]
  counts: MaskCounts
}

type Verdict = keyof MaskCounts

/** The text a masked result is replaced with; the same arguments always give the same text. */
export function placeholder(tool: string, chars: number, path: string): string {
  return `${MARK_PREFIX}: ${tool} result (${chars} chars) moved to ${path} to save context. Earlier turns saw the full content and their conclusions still stand. Read that file with the Read tool only if you need the exact text again.]`
}

/** A user row without tool results whose text, after leading whitespace, begins with none of `ENGINE_ROW_PREFIXES`. */
function isHumanPrompt(message: SessionMessage): boolean {
  if (message.role !== 'user' || (message.toolResults !== undefined && message.toolResults.length > 0)) return false
  const text = message.text.trimStart()
  return !ENGINE_ROW_PREFIXES.some((prefix) => text.startsWith(prefix))
}

function resultsOf(message: SessionMessage): readonly ToolResult[] {
  return message.role === 'user' ? (message.toolResults ?? []) : []
}

/**
 * The index of the oldest of the last `keep` human prompts: rows from it on are recent.
 * With fewer human prompts than `keep` (or a `keep` that never compares true) every row is recent;
 * with `keep` 0 or below none is.
 */
function recentStart(messages: readonly SessionMessage[], keep: number): number {
  if (keep <= 0) return messages.length
  let seen = 0
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (!isHumanPrompt(messages[index])) continue
    seen += 1
    if (seen >= keep) return index
  }
  return 0
}

/** The first reason that keeps one result, else `mask`. A size threshold that compares false (NaN) keeps it. */
function verdictOf(result: ToolResult, tool: string, opts: MaskOptions): Verdict {
  if (result.isError) return 'error'
  if (opts.imageIds.has(result.tool_use_id)) return 'image'
  if (!ALLOWED_TOOLS.has(tool)) return 'tool'
  if (result.text.startsWith(MARK_PREFIX)) return 'already'
  if (!(result.text.length >= opts.minMaskChars)) return 'small'
  return 'mask'
}

/**
 * Picks the tool results to mask, whole user rows only.
 *
 * Each tool result of a user row is counted once. A row at or after the oldest of the last
 * `keepRecentUserTurns` human prompts (`isHumanPrompt`: user rows without tool results, less the rows
 * the engine writes, `ENGINE_ROW_PREFIXES`) counts all its results as `recent`. Leaving those engine
 * rows out can only move that boundary earlier: every row recent with them counted is recent without.
 * Elsewhere a result takes the first reason that keeps it (`error`, `image`, `tool`,
 * `already`, `small`), else `mask`. A row holding any kept result yields no candidate, and its
 * would-be masks are counted under the first kept reason in that row, so `counts.mask` always
 * equals `candidates.length`. Tool names come from the assistant rows' `toolUses`; a result whose
 * id no tool_use carries counts as `tool`.
 */
export function selectMasks(messages: readonly SessionMessage[], opts: MaskOptions): MaskSelection {
  const toolOf = new Map<string, string>()
  for (const message of messages) {
    if (message.role !== 'assistant') continue
    for (const use of message.toolUses ?? []) toolOf.set(use.tool_use_id, use.tool)
  }
  const recentFrom = recentStart(messages, opts.keepRecentUserTurns)
  const counts: MaskCounts = { mask: 0, recent: 0, error: 0, image: 0, tool: 0, small: 0, already: 0 }
  const candidates: MaskCandidate[] = []
  for (const [messageIndex, message] of messages.entries()) {
    const results = resultsOf(message)
    if (results.length === 0) continue
    if (messageIndex >= recentFrom) {
      counts.recent += results.length
      continue
    }
    const judged = results.map((result) => {
      const tool = toolOf.get(result.tool_use_id) ?? ''
      return { result, tool, verdict: verdictOf(result, tool, opts) }
    })
    const kept = judged.find((entry) => entry.verdict !== 'mask')
    if (kept !== undefined) {
      for (const entry of judged) counts[entry.verdict === 'mask' ? kept.verdict : entry.verdict] += 1
      continue
    }
    counts.mask += judged.length
    for (const entry of judged) {
      candidates.push({
        messageIndex,
        tool_use_id: entry.result.tool_use_id,
        tool: entry.tool,
        chars: entry.result.text.length,
        text: entry.result.text,
      })
    }
  }
  return { candidates, counts }
}

/**
 * The transcript with every user row whose each tool_use_id has a replacement masked: a new object
 * whose results keep their order and ids with only `text` replaced (`isError` false, no `result`),
 * and with no `handle`, so the engine reads it as built. Every other row is the original object
 * itself, handle and all, so the engine keeps it whole.
 */
export function applyMasks(messages: readonly SessionMessage[], replacements: ReadonlyMap<string, string>): SessionMessage[] {
  return messages.map((message) => {
    const results = resultsOf(message)
    if (results.length === 0) return message
    const toolResults: ToolResult[] = []
    for (const result of results) {
      const text = replacements.get(result.tool_use_id)
      if (text === undefined) return message
      toolResults.push({ tool_use_id: result.tool_use_id, text, isError: false })
    }
    return { role: message.role, text: message.text, toolUses: message.toolUses, toolResults }
  })
}

/** Whether two lists name the same tool_use_ids in the same order. */
function isSameIds(a: readonly { tool_use_id: string }[], b: readonly { tool_use_id: string }[]): boolean {
  return a.length === b.length && a.every((entry, index) => entry.tool_use_id === b[index].tool_use_id)
}

/**
 * Whether `message` repeats `kept`, the row kept just before it. An assistant row repeats one of the same text and
 * the same tool_use ids in order, when it has text or a tool use; a user row of tool results repeats one of the same
 * text and the same result ids in order, whatever the results' text. A user row without tool results, a human prompt
 * or a row the engine writes, repeats nothing.
 */
function isRepeatOf(message: SessionMessage, kept: SessionMessage): boolean {
  if (message.role !== kept.role || message.text !== kept.text) return false
  if (message.role === 'assistant') {
    const uses = message.toolUses ?? []
    return (message.text !== '' || uses.length > 0) && isSameIds(uses, kept.toolUses ?? [])
  }
  const results = resultsOf(message)
  return results.length > 0 && isSameIds(results, resultsOf(kept))
}

/**
 * The transcript with every row that repeats the row kept just before it dropped, so a run of any length folds to
 * its first row, kept as the very object it was, handle and all. A resumed session's loader gathers every row of the
 * file that carries one API message id, and a compaction this plugin answered is stored as copies under the
 * originals' ids, so a resume hands such a row back once more for each copy, one after another (a tool result's copy
 * may be its placeholder). With nothing dropped, `messages` is a new array of the same rows.
 */
export function dropRepeatedRows(messages: readonly SessionMessage[]): { messages: SessionMessage[]; dropped: number } {
  const kept: SessionMessage[] = []
  for (const message of messages) {
    if (kept.length > 0 && isRepeatOf(message, kept[kept.length - 1])) continue
    kept.push(message)
  }
  return { messages: kept, dropped: messages.length - kept.length }
}
