import type { SessionMessage } from 'claude-code'
import { test, expect } from 'claude-code/testing'
import { ALLOWED_TOOLS, MARK_PREFIX, applyMasks, dropRepeatedRows, placeholder, selectMasks } from '../lib/policy.ts'
import type { MaskCandidate, MaskCounts } from '../lib/policy.ts'

const OPTS = { keepRecentUserTurns: 6, minMaskChars: 1200, imageIds: new Set<string>() }
const COUNT_KEYS = ['mask', 'recent', 'error', 'image', 'tool', 'small', 'already'] as const
const ENGINE_MARKERS = ['<task-notification>', '<local-command-caveat>', '<local-command-stdout>', '<local-command-stderr>', 'Base directory for this skill:'] as const

function prompt(text: string): SessionMessage {
  return { role: 'user', text, toolUses: [] }
}

function reply(text: string): SessionMessage {
  return { role: 'assistant', text, toolUses: [] }
}

function notification(id: string): SessionMessage {
  return prompt(`<task-notification>\n<task-id>${id}</task-id>\n<status>completed</status>\n</task-notification>`)
}

function calls(uses: readonly (readonly [string, string])[]): SessionMessage {
  return { role: 'assistant', text: '', toolUses: uses.map(([tool_use_id, tool]) => ({ tool_use_id, tool, input: {} })) }
}

function results(rows: readonly { id: string; text: string; isError?: boolean }[]): SessionMessage {
  return {
    role: 'user',
    text: '',
    toolUses: [],
    toolResults: rows.map((row) => ({ tool_use_id: row.id, text: row.text, isError: row.isError ?? false, result: { stored: row.id } })),
    handle: `handle-${rows.map((row) => row.id).join('-')}`,
  }
}

function laterTurns(count: number): SessionMessage[] {
  const out: SessionMessage[] = []
  for (let i = 0; i < count; i += 1) out.push(prompt(`later prompt ${i}`), reply(`later answer ${i}`))
  return out
}

function big(fill: string, length = 1500): string {
  return fill.repeat(length)
}

function spillMap(candidates: readonly MaskCandidate[]): Map<string, string> {
  return new Map(candidates.map((c): [string, string] => [c.tool_use_id, placeholder(c.tool, c.chars, `/spill/s1/${c.tool_use_id}.txt`)]))
}

function expectCounts(actual: MaskCounts, want: Partial<MaskCounts>): void {
  expect(Object.keys(actual).join(',')).toBe(COUNT_KEYS.join(','))
  for (const key of COUNT_KEYS) expect(`${key}=${actual[key]}`).toBe(`${key}=${want[key] ?? 0}`)
}

test('policy: masks eligible result', () => {
  const messages = [
    prompt('look around'),
    calls([['t1', 'Read'], ['t2', 'Grep'], ['t3', 'Glob'], ['t4', 'Bash']]),
    results([{ id: 't1', text: big('a') }, { id: 't2', text: big('b', 1300) }, { id: 't3', text: big('c', 1400) }, { id: 't4', text: big('d', 2000) }]),
    reply('found it'),
    ...laterTurns(6),
  ]
  const { candidates, counts } = selectMasks(messages, OPTS)
  expectCounts(counts, { mask: 4 })
  expect(candidates.map((c) => `${c.messageIndex}:${c.tool_use_id}:${c.tool}:${c.chars}`).join(' ')).toBe('2:t1:Read:1500 2:t2:Grep:1300 2:t3:Glob:1400 2:t4:Bash:2000')
  expect(candidates.map((c) => c.text).join('|')).toBe([big('a'), big('b', 1300), big('c', 1400), big('d', 2000)].join('|'))
  expect([...ALLOWED_TOOLS].sort().join(',')).toBe('Bash,Glob,Grep,Read')

  const shown = placeholder('Read', 1500, '/spill/s1/t1.txt')
  expect(shown).toBe('[fz-compact: Read result (1500 chars) moved to /spill/s1/t1.txt to save context. Earlier turns saw the full content and their conclusions still stand. Read that file with the Read tool only if you need the exact text again.]')
  expect(shown.startsWith(MARK_PREFIX)).toBe(true)

  const replacements = spillMap(candidates)
  const out = applyMasks(messages, replacements)
  expect(out.length).toBe(messages.length)
  expect(out.every((m, i) => i === 2 || m === messages[i])).toBe(true)
  const row = out[2]
  expect(row === messages[2]).toBe(false)
  expect('handle' in row).toBe(false)
  expect(`${row.role}|${row.text}`).toBe('user|')
  expect((row.toolResults ?? []).map((r) => r.tool_use_id).join(',')).toBe('t1,t2,t3,t4')
  expect((row.toolResults ?? []).every((r) => r.text === replacements.get(r.tool_use_id) && r.isError === false && !('result' in r))).toBe(true)
  expect(messages[2].handle).toBe('handle-t1-t2-t3-t4')
  expect(messages[2].toolResults?.[0]?.text).toBe(big('a'))
})

test('policy: keeps recent', () => {
  const head = [prompt('first'), calls([['t1', 'Read']]), results([{ id: 't1', text: big('a') }]), reply('read it')]

  const inside = [...head, ...laterTurns(5)]
  const kept = selectMasks(inside, OPTS)
  expect(kept.candidates.length).toBe(0)
  expectCounts(kept.counts, { recent: 1 })
  expect(applyMasks(inside, spillMap(kept.candidates)).every((m, i) => m === inside[i])).toBe(true)

  const busy = [...head]
  for (let i = 0; i < 6; i += 1) busy.push(calls([[`b${i}`, 'Bash']]), results([{ id: `b${i}`, text: 'ok' }]))
  expectCounts(selectMasks(busy, OPTS).counts, { recent: 7 })

  const outside = [...head, ...laterTurns(6)]
  const moved = selectMasks(outside, OPTS)
  expect(moved.candidates.map((c) => c.tool_use_id).join(',')).toBe('t1')
  expectCounts(moved.counts, { mask: 1 })
  expectCounts(selectMasks(outside, { ...OPTS, keepRecentUserTurns: 7 }).counts, { recent: 1 })

  const emptyResults: SessionMessage = { role: 'user', text: 'one more', toolUses: [], toolResults: [] }
  expectCounts(selectMasks([...head, ...laterTurns(5), emptyResults], OPTS).counts, { mask: 1 })
})

test('policy: engine rows are not prompts', () => {
  expect(ENGINE_MARKERS.every((marker) => /^(<[a-z-]+>|[A-Za-z :]+)$/.test(marker))).toBe(true)
  expect(notification('n').text.startsWith(ENGINE_MARKERS[0])).toBe(true)

  const head = [prompt('build it in the background'), calls([['t1', 'Bash']]), results([{ id: 't1', text: big('a') }]), reply('started')]
  expectCounts(selectMasks([...head, ...laterTurns(6)], OPTS).counts, { mask: 1 })

  const notified = [...head]
  for (let i = 0; i < 6; i += 1) notified.push(notification(`n${i}`), reply(`noted ${i}`))
  const kept = selectMasks(notified, OPTS)
  expect(kept.candidates.length).toBe(0)
  expectCounts(kept.counts, { recent: 1 })

  for (const marker of ENGINE_MARKERS) {
    const rows = [...head]
    for (let i = 0; i < 6; i += 1) rows.push(prompt(`\n  ${marker} row ${i}`), reply(`ok ${i}`))
    const sel = selectMasks(rows, OPTS)
    expect(`${marker} -> mask=${sel.counts.mask} recent=${sel.counts.recent}`).toBe(`${marker} -> mask=0 recent=1`)
  }

  expectCounts(selectMasks([...notified, ...laterTurns(6)], OPTS).counts, { mask: 1 })
})

test('policy: skill body counts with its slash command', () => {
  const messages = [
    prompt('read the plan'),
    calls([['t1', 'Read']]),
    results([{ id: 't1', text: big('p') }]),
    reply('read it'),
    prompt('<command-message>fz-code</command-message>\n<command-name>/fz-code</command-name>\n<command-args>step 3</command-args>'),
    prompt('Base directory for this skill: /plugins/fz/skills/fz-code\n\n# fz-code\nRun the step.'),
    reply('on it'),
  ]
  const two = selectMasks(messages, { ...OPTS, keepRecentUserTurns: 2 })
  expect(two.candidates.length).toBe(0)
  expectCounts(two.counts, { recent: 1 })

  const one = selectMasks(messages, { ...OPTS, keepRecentUserTurns: 1 })
  expect(one.candidates.map((c) => c.tool_use_id).join(',')).toBe('t1')
  expectCounts(one.counts, { mask: 1 })
})

test('policy: marker inside a prompt still counts', () => {
  const build = (question: string): SessionMessage[] => {
    const rows = [
      prompt('first'),
      calls([['t1', 'Read']]),
      results([{ id: 't1', text: big('a') }]),
      reply('read it'),
      prompt(question),
      calls([['t2', 'Read']]),
      results([{ id: 't2', text: big('b') }]),
      reply('read that too'),
    ]
    for (let i = 0; i < 6; i += 1) rows.push(notification(`n${i}`), reply(`noted ${i}`))
    return rows
  }
  const sel = selectMasks(build(`why did a ${ENGINE_MARKERS[0]} arrive just now?`), { ...OPTS, keepRecentUserTurns: 1 })
  expect(sel.candidates.map((c) => c.tool_use_id).join(',')).toBe('t1')
  expectCounts(sel.counts, { mask: 1, recent: 1 })

  for (const marker of ENGINE_MARKERS) {
    const quoted = selectMasks(build(`what does ${marker} mean here?`), { ...OPTS, keepRecentUserTurns: 1 })
    expect(`${marker} -> ${quoted.candidates.map((c) => c.tool_use_id).join(',')}`).toBe(`${marker} -> t1`)
  }
})

test('policy: keeps error', () => {
  const build = (isError: boolean): SessionMessage[] => [
    prompt('run it'),
    calls([['t1', 'Bash']]),
    results([{ id: 't1', text: big('e'), isError }]),
    reply('it failed'),
    ...laterTurns(6),
  ]
  const failed = selectMasks(build(true), OPTS)
  expect(failed.candidates.length).toBe(0)
  expectCounts(failed.counts, { error: 1 })
  expectCounts(selectMasks(build(false), OPTS).counts, { mask: 1 })
})

test('policy: keeps image', () => {
  const messages = [prompt('show me'), calls([['t1', 'Read']]), results([{ id: 't1', text: big('i') }]), reply('a picture'), ...laterTurns(6)]
  const withImage = selectMasks(messages, { ...OPTS, imageIds: new Set(['t1']) })
  expect(withImage.candidates.length).toBe(0)
  expectCounts(withImage.counts, { image: 1 })
  expectCounts(selectMasks(messages, { ...OPTS, imageIds: new Set(['t9']) }).counts, { mask: 1 })
})

test('policy: keeps non-allowed tool', () => {
  const messages = [
    prompt('delegate'),
    calls([['a1', 'Agent'], ['w1', 'Workflow'], ['s1', 'Skill'], ['m1', 'mcp__server__tool'], ['g1', 'Glob']]),
    results([{ id: 'a1', text: big('a') }]),
    results([{ id: 'w1', text: big('w') }]),
    results([{ id: 's1', text: big('s') }]),
    results([{ id: 'm1', text: big('m') }]),
    results([{ id: 'orphan', text: big('o') }]),
    results([{ id: 'g1', text: big('g') }]),
    reply('done'),
    ...laterTurns(6),
  ]
  const sel = selectMasks(messages, OPTS)
  expect(sel.candidates.map((c) => `${c.tool_use_id}:${c.tool}`).join(',')).toBe('g1:Glob')
  expectCounts(sel.counts, { mask: 1, tool: 5 })
  expect(['Agent', 'Workflow', 'Skill', 'mcp__server__tool'].some((tool) => ALLOWED_TOOLS.has(tool))).toBe(false)
})

test('policy: keeps small', () => {
  const messages = [
    prompt('peek'),
    calls([['t1', 'Read'], ['t2', 'Read']]),
    results([{ id: 't1', text: big('s', 1199) }]),
    results([{ id: 't2', text: big('m', 1200) }]),
    reply('ok'),
    ...laterTurns(6),
  ]
  const sel = selectMasks(messages, OPTS)
  expect(sel.candidates.map((c) => `${c.tool_use_id}:${c.chars}`).join(',')).toBe('t2:1200')
  expectCounts(sel.counts, { mask: 1, small: 1 })
  expectCounts(selectMasks(messages, { ...OPTS, minMaskChars: 1199 }).counts, { mask: 2 })
})

test('policy: skips already masked', () => {
  const messages = [
    prompt('again'),
    calls([['t1', 'Read'], ['t2', 'Bash']]),
    results([{ id: 't1', text: big('a') }]),
    results([{ id: 't2', text: `${MARK_PREFIX}: earlier marker ${big('z')}` }]),
    reply('ok'),
    ...laterTurns(6),
  ]
  const first = selectMasks(messages, OPTS)
  expect(first.candidates.map((c) => c.tool_use_id).join(',')).toBe('t1')
  expectCounts(first.counts, { mask: 1, already: 1 })

  const masked = applyMasks(messages, spillMap(first.candidates))
  const shown = masked[2].toolResults?.[0]?.text ?? ''
  expect(shown).toBe(placeholder('Read', 1500, '/spill/s1/t1.txt'))
  expect(shown.length < OPTS.minMaskChars).toBe(true)

  const second = selectMasks(masked, OPTS)
  expect(second.candidates.length).toBe(0)
  expectCounts(second.counts, { already: 2 })
  expect(applyMasks(masked, spillMap(second.candidates)).every((m, i) => m === masked[i])).toBe(true)
})

test('policy: keeps mixed row whole', () => {
  const messages = [
    prompt('mixed'),
    calls([['t1', 'Read'], ['t2', 'Read'], ['g1', 'Grep'], ['a1', 'Agent']]),
    results([{ id: 't1', text: big('a') }, { id: 't2', text: big('b'), isError: true }]),
    results([{ id: 'g1', text: big('g') }, { id: 'a1', text: big('h') }]),
    reply('mixed'),
    ...laterTurns(6),
  ]
  const sel = selectMasks(messages, OPTS)
  expect(sel.candidates.length).toBe(0)
  expectCounts(sel.counts, { error: 2, tool: 2 })
  expect(applyMasks(messages, spillMap(sel.candidates)).every((m, i) => m === messages[i])).toBe(true)

  const partial = applyMasks(messages, new Map([['t1', placeholder('Read', 1500, '/spill/s1/t1.txt')]]))
  expect(partial[2] === messages[2]).toBe(true)

  const whole = applyMasks(messages, new Map([['t1', 'mask one'], ['t2', 'mask two']]))
  expect(whole[2] === messages[2]).toBe(false)
  expect((whole[2].toolResults ?? []).map((r) => `${r.tool_use_id}=${r.text}`).join(',')).toBe('t1=mask one,t2=mask two')
  expect(whole[3] === messages[3]).toBe(true)
})

test('policy: drops repeated rows', () => {
  const shown = placeholder('Read', 1500, '/spill/s1/t1.txt')
  const messages = [
    prompt('read it'),
    calls([['t1', 'Read']]),
    calls([['t1', 'Read']]),
    results([{ id: 't1', text: big('a') }]),
    results([{ id: 't1', text: shown }]),
    reply('thinking it over'),
    reply('thinking it over'),
    reply('thinking it over'),
    prompt('again'),
    prompt('again'),
    reply('between'),
    prompt('in between'),
    reply('between'),
    reply(''),
    reply(''),
  ]
  const out = dropRepeatedRows(messages)
  expect(out.dropped).toBe(4)
  expect(out.messages.map((m) => [m.role, m.text, ...(m.toolUses ?? []).map((u) => u.tool_use_id), ...(m.toolResults ?? []).map((r) => `${r.tool_use_id}=${r.text.length}`)].join('|')).join(',')).toBe(
    [
      'user|read it',
      'assistant||t1',
      'user||t1=1500',
      'assistant|thinking it over',
      'user|again',
      'user|again',
      'assistant|between',
      'user|in between',
      'assistant|between',
      'assistant|',
      'assistant|',
    ].join(','),
  )
  // The first row of each run is kept as the input's own object, handle and original result included.
  expect(out.messages.map((m) => messages.indexOf(m)).join(',')).toBe('0,1,3,5,8,9,10,11,12,13,14')
  expect(out.messages[1] === messages[1]).toBe(true)
  expect(out.messages[2] === messages[3]).toBe(true)
  expect(out.messages[2].handle).toBe('handle-t1')
  expect(out.messages[2].toolResults?.[0]?.text).toBe(big('a'))
  expect(out.messages[3] === messages[5]).toBe(true)

  const clean = [prompt('first'), calls([['t1', 'Read']]), results([{ id: 't1', text: big('a') }]), reply('done')]
  const same = dropRepeatedRows(clean)
  expect(same.dropped).toBe(0)
  expect(same.messages === clean).toBe(false)
  expect(same.messages.length).toBe(clean.length)
  expect(same.messages.every((m, i) => m === clean[i])).toBe(true)
})
