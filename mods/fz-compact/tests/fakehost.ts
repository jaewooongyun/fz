import type { SpillHost } from '../lib/spill.ts'

/**
 * One file of the memory file system. `size`, when set, is what `list` and `stat` report in place of the
 * text's UTF-8 length, so a test can fill a folder without building the bytes.
 */
export type FakeFile = {
  text: string
  mtimeMs: number
  size?: number
}

/** How an injected `process.run` failure shows: a non-zero exit, or a rejected call. */
export type RunFailure = 'exit' | 'reject'

/**
 * A `SpillHost` over memory, with the knobs a test turns. Files live in `files` (path to file) and folders
 * in `dirs`, made for every parent a write, a move or `put` touches; a write stamps `nowMs`, and `mv -f`
 * keeps the moved file's stamp, as a rename does. `process.run` reads `mv -f <from> <to>` and
 * `rm -f <path>...`, nothing else. Every call is logged in `calls` in order (`read <path>`, `write <path>`,
 * `list <path>`, `stat <path>`, `exists <path>`, `run <argv joined by spaces>`, and `mark <label>` from the
 * test) and yields once, so concurrent callers interleave.
 */
export type FakeHost = SpillHost & {
  files: Map<string, FakeFile>
  dirs: Set<string>
  calls: string[]
  nowMs: number
  /** A read of an existing file this accepts rejects, as a refused or failed read does. */
  failRead: (path: string) => boolean
  /** A write to a path this accepts stores half the text, as a torn write would, and rejects. */
  failWrite: (path: string) => boolean
  /** A `process.run` this names a failure for fails that way, before the command is read. */
  failRun: (argv: readonly string[]) => RunFailure | undefined
  /** A read of an existing file this gives a text for answers that text in place of the stored one. */
  readAs: (path: string) => string | undefined
  /** A `stat` of a file listed here reports this mtime; `list` still reports the stored one. */
  statMtime: Map<string, number>
  /** Seeds a file without logging a call. */
  put(path: string, text: string, mtimeMs: number, size?: number): void
  mark(label: string): void
}

type RunResult = { exitCode: number; stdout: string; stderr: string }
type FakeEntry = { name: string; kind: 'file' | 'dir' | 'other'; size: number; mtimeMs: number }

function tick(): Promise<void> {
  return Promise.resolve()
}

function parentOf(path: string): string {
  const cut = path.lastIndexOf('/')
  return cut <= 0 ? '/' : path.slice(0, cut)
}

function nameOf(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

function addParents(dirs: Set<string>, path: string): void {
  for (let dir = parentOf(path); dir !== '/' && !dirs.has(dir); dir = parentOf(dir)) dirs.add(dir)
}

function sizeOf(file: FakeFile): number {
  return file.size ?? new TextEncoder().encode(file.text).length
}

function exited(exitCode: number, stderr = ''): RunResult {
  return { exitCode, stdout: '', stderr }
}

function move(host: FakeHost, from: string, to: string): RunResult {
  const file = host.files.get(from)
  if (file === undefined || !host.dirs.has(parentOf(to))) return exited(1, `mv: ${from}: No such file or directory`)
  host.files.delete(from)
  host.files.set(to, file)
  return exited(0)
}

function remove(host: FakeHost, paths: readonly string[]): RunResult {
  let exitCode = 0
  for (const path of paths) {
    if (host.dirs.has(path)) exitCode = 1
    else host.files.delete(path)
  }
  return exited(exitCode, exitCode === 0 ? '' : 'rm: is a directory')
}

export function fakeHost(nowMs = 0): FakeHost {
  const host: FakeHost = {
    files: new Map(),
    dirs: new Set(),
    calls: [],
    nowMs,
    failRead: () => false,
    failWrite: () => false,
    failRun: () => undefined,
    readAs: () => undefined,
    statMtime: new Map(),
    put(path, text, mtimeMs, size) {
      host.files.set(path, size === undefined ? { text, mtimeMs } : { text, mtimeMs, size })
      addParents(host.dirs, path)
    },
    mark(label) {
      host.calls.push(`mark ${label}`)
    },
    fs: {
      async read(path) {
        host.calls.push(`read ${path}`)
        await tick()
        const file = host.files.get(path)
        if (file === undefined) throw new Error(`ENOENT: ${path}`)
        if (host.failRead(path)) throw new Error(`EACCES: ${path}`)
        return host.readAs(path) ?? file.text
      },
      async write(path, text) {
        host.calls.push(`write ${path}`)
        await tick()
        const torn = host.failWrite(path)
        host.files.set(path, { text: torn ? text.slice(0, Math.floor(text.length / 2)) : text, mtimeMs: host.nowMs })
        addParents(host.dirs, path)
        if (torn) throw new Error(`EIO: ${path}`)
      },
      async list(path) {
        host.calls.push(`list ${path}`)
        await tick()
        if (!host.dirs.has(path)) throw new Error(`ENOENT: ${path}`)
        const entries: FakeEntry[] = []
        for (const dir of host.dirs) if (parentOf(dir) === path) entries.push({ name: nameOf(dir), kind: 'dir', size: 0, mtimeMs: 0 })
        for (const [file, data] of host.files) if (parentOf(file) === path) entries.push({ name: nameOf(file), kind: 'file', size: sizeOf(data), mtimeMs: data.mtimeMs })
        return entries
      },
      async stat(path) {
        host.calls.push(`stat ${path}`)
        await tick()
        const file = host.files.get(path)
        if (file !== undefined) return { kind: 'file', size: sizeOf(file), mtimeMs: host.statMtime.get(path) ?? file.mtimeMs, isLink: false }
        if (host.dirs.has(path)) return { kind: 'dir', size: 0, mtimeMs: 0, isLink: false }
        throw new Error(`ENOENT: ${path}`)
      },
      async exists(path) {
        host.calls.push(`exists ${path}`)
        await tick()
        return host.files.has(path) || host.dirs.has(path)
      },
    },
    process: {
      async run(argv) {
        host.calls.push(`run ${argv.join(' ')}`)
        await tick()
        const failure = host.failRun(argv)
        if (failure === 'reject') throw new Error(`injected rejection: ${argv.join(' ')}`)
        if (failure === 'exit') return exited(1, 'injected failure')
        const [command, flag, ...rest] = argv
        if (command === 'mv' && flag === '-f' && rest.length === 2) return move(host, rest[0] ?? '', rest[1] ?? '')
        if (command === 'rm' && flag === '-f') return remove(host, rest)
        return exited(127, `unknown command: ${argv.join(' ')}`)
      },
    },
  }
  return host
}
