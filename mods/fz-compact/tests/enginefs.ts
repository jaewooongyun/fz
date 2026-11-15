import type { On } from 'claude-code'
import { fakeHost } from './fakehost.ts'
import type { FakeHost } from './fakehost.ts'

/**
 * The fake host of `tests/fakehost.ts` standing beneath the plugin under test as the engine's file system and
 * `process.run`: the test's own hooks (`fs.read`, `fs.write`, `fs.list`, `fs.stat`, `fs.exists`, `process.run`)
 * answer each call from it with `{ value }`, or `{ deny }` where it rejects, which rejects the plugin's call. Its
 * files, folders, call log, `put`, and its reading of `mv -f` and `rm -f` are the ones the spill tests run on; a
 * write stamps the `now` handed to `engineFs`.
 */
export type EngineFs = FakeHost & {
  /**
   * Paths `stat` answers as symbolic links, each to the path it maps to, matched whole (a path beneath one is not
   * followed through it): `kind`, `size` and `mtimeMs` are the target's, and with `{ resolve: true }` `realPath` is
   * the target when something is there. A target with nothing at it is a link that leads nowhere: `other`, with no
   * `realPath`.
   */
  realPaths: Map<string, string>
}

type Stat = Awaited<ReturnType<FakeHost['fs']['stat']>>

/** A call on `$` as the engine's hooks answer it. */
type Answer<T> = { value: T } | { deny: string }

/** `work`'s value, or its rejection's message as the deny. */
async function answer<T>(work: () => Promise<T>): Promise<Answer<T>> {
  try {
    return { value: await work() }
  } catch (error) {
    return { deny: error instanceof Error ? error.message : String(error) }
  }
}

/** What `stat` answers for a path of `realPaths`, logged as the fake host logs its own. */
function linkStatOf(disk: EngineFs, path: string, target: string, resolve: boolean): Stat {
  disk.calls.push(`stat ${path}`)
  const file = disk.files.get(target)
  const isDir = disk.dirs.has(target)
  const stat: Stat =
    file !== undefined
      ? { kind: 'file', size: file.size ?? new TextEncoder().encode(file.text).length, mtimeMs: file.mtimeMs, isLink: true }
      : { kind: isDir ? 'dir' : 'other', size: 0, mtimeMs: 0, isLink: true }
  if (resolve && (file !== undefined || isDir)) stat.realPath = target
  return stat
}

/** What `stat` answers for `path`: a link of `realPaths` as one, else the fake host's own, `realPath` the path itself when asked. */
async function statOf(disk: EngineFs, path: string, resolve: boolean): Promise<Stat> {
  const target = disk.realPaths.get(path)
  if (target !== undefined) return linkStatOf(disk, path, target, resolve)
  const stat = await disk.fs.stat(path)
  return resolve ? { ...stat, realPath: path } : stat
}

/**
 * Registers the hooks on the test's `on` and hands back the file system they answer from. Call it once per test,
 * before the test's first call on `$`: a second hook of the test on one event needs a matcher.
 */
export function engineFs(on: On, now: () => number): EngineFs {
  const disk: EngineFs = Object.assign(fakeHost(now()), { realPaths: new Map<string, string>() })
  on('fs.read', (_, e) => answer(() => disk.fs.read(e.path)))
  on('fs.write', (_, e) => {
    disk.nowMs = now()
    return answer(() => disk.fs.write(e.path, e.text))
  })
  on('fs.list', (_, e) => answer(async () => (await disk.fs.list(e.path)).map((entry) => ({ ...entry, isLink: false }))))
  on('fs.stat', (_, e) => answer(() => statOf(disk, e.path, e.resolve)))
  on('fs.exists', (_, e) => answer(() => disk.fs.exists(e.path)))
  on('process.run', (_, e) => answer(async () => ({ ...(await disk.process.run(e.argv)), isStdoutTruncated: false, isStderrTruncated: false })))
  return disk
}
