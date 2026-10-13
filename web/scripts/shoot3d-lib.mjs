// Headless Chromium from the Playwright cache (macOS, Linux, Windows), or PLAYWRIGHT_CHROMIUM.
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export function chromiumPath() {
  if (process.env.PLAYWRIGHT_CHROMIUM) return process.env.PLAYWRIGHT_CHROMIUM;
  const caches = [join(homedir(), "Library/Caches/ms-playwright"), join(homedir(), ".cache/ms-playwright"), join(process.env.LOCALAPPDATA ?? "", "ms-playwright")];
  for (const cache of caches.filter(existsSync))
    for (const d of readdirSync(cache).filter((x) => x.startsWith("chromium_headless_shell-")).sort().reverse())
      for (const sub of readdirSync(join(cache, d)))
        for (const exe of ["chrome-headless-shell", "chrome-headless-shell.exe"]) {
          const p = join(cache, d, sub, exe);
          if (existsSync(p)) return p;
        }
  return undefined;
}
