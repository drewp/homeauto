import builtins from "rollup-plugin-node-builtins";
import commonjs from '@rollup/plugin-commonjs';
import resolve from "@rollup/plugin-node-resolve";
import typescript from "rollup-plugin-typescript2";

export default {
    input: "src/index.ts",
    output: {
        file: "build/bundle.js",
        format: "esm",
       // intro: "const global = window;"
    },
    plugins: [
        builtins(),
        resolve({
            extensions: [".js", ".ts"],
            browser: true
        }),
        typescript(),
        commonjs({
            namedExports: {
                'jsonld': ['expand'], // fixes "expand is not exported by node_modules/jsonld/lib/index.js"
            }
        }),
    ]
};
