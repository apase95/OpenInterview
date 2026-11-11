import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
const require = createRequire(import.meta.url);
const swc = require("next/dist/build/swc");
await swc.loadBindings();
const cache = new Map();
export function load(file) {
  const path = resolve(file);
  if (cache.has(path)) return cache.get(path).exports;
  const module = { exports: {} };
  cache.set(path, module);
  const source = readFileSync(path, "utf8");
  const output = swc.transformSync(source, {
    filename: path,
    jsc: {
      parser: { syntax: "typescript", tsx: true },
      transform: { react: { runtime: "automatic" } },
    },
    module: { type: "commonjs" },
  }).code;
  new Function("require", "module", "exports", output)(
    (name) => {
      if (name.endsWith(".css"))
        return new Proxy(
          {},
          { get: (_, key) => (key === "__esModule" ? false : String(key)) },
        );
      if (name === "next/navigation")
        return { useRouter: () => ({ push() {}, replace() {} }) };
      if (name.startsWith(".") && name.endsWith(".json"))
        return require(resolve(dirname(path), name));
      if (name.startsWith(".")) {
        const target = resolve(dirname(path), name);
        for (const suffix of ["", ".tsx", ".ts", ".mjs"])
          if (existsSync(target + suffix)) return load(target + suffix);
      }
      return require(name);
    },
    module,
    module.exports,
  );
  return module.exports;
}
