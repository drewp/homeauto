import builtins from "rollup-plugin-node-builtins";
import commonjs from "@rollup/plugin-commonjs";
import resolve from "@rollup/plugin-node-resolve";
import typescript from "rollup-plugin-typescript2";
import replace from "@rollup/plugin-replace";

const workaround_jsonld_module_system_picker = "process = {version: '1.0.0'}";
const workaround_some_browser_detector = "global = window";

// This makes <dom-module> element totally unavailable. I only meant to prune one of the
// two, but of course why is streamed-graph's node_modules/**/dom-module.js file getting 
// here in the first place?
const duplicated_line_i_cant_prune =
  "customElements.define('dom-module', DomModule);";
const replacements = {};
replacements[duplicated_line_i_cant_prune] = "";

export default {
  input: "src/index.ts",
  output: {
    file: "build/bundle.js",
    format: "esm",
    intro: `const ${workaround_some_browser_detector}, ${workaround_jsonld_module_system_picker};`,
  },
  external: [
    "dom-module", // don't want two of these in the bundle
  ],
  plugins: [
    builtins(),
    resolve({
      extensions: [".js", ".ts"],
      browser: true,
    }),
    typescript(),
    commonjs({
      namedExports: {
        jsonld: ["expand"], // fixes "expand is not exported by node_modules/jsonld/lib/index.js"
      },
    }),
    replace({ ...replacements, delimiters: ["", ""] }),
  ],
};
