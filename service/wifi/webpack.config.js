const glob = require('glob');
const jest = require('jest');
const path = require("path");
const PnpWebpackPlugin = require('pnp-webpack-plugin');

const base = {
    devtool: 'source-map',
    module: {
        rules: [
            {
                test: /\.ts$/,
                loader: require.resolve('ts-loader'),
                options: PnpWebpackPlugin.tsLoaderOptions({})
            },
            {
                test: /\.css$/i,
                use: ['file-loader']
            },
        ]
    },
    resolve: {
        extensions: [".ts", ".js"],
        plugins: [
            PnpWebpackPlugin,
        ],
        alias: {
            'streamed-graph': '/my/proj/streamed-graph'
        },
        modules: ['/tmp/sgpath2'],
    },
    resolveLoader: { plugins: [PnpWebpackPlugin.moduleLoader(module),], }
};

function outputToBundle(bundleName) {
    return {
        filename: bundleName,
        path: path.resolve(__dirname, 'build'),
        publicPath: '/build/'
    };
}

module.exports = [
    Object.assign({
        name: "main",
        entry: ['./src/wifi.ts'],
        output: outputToBundle('wifi.bundle.js'),
        devServer: {
            port: 8082,
            publicPath: '/build/',
            contentBase: __dirname
        }
    }, base),
    Object.assign({
        name: "test",
        entry: glob.sync('src/**/*.test.ts').map((p) => './' + p),
        output: outputToBundle('test.bundle.js'),
        plugins: [
            {
                apply: (compiler) => {
                    compiler.hooks.afterEmit.tap('AfterEmitPlugin', (compilation) => {
                        jest.run([
                            '--detectOpenHandles', // not just to debug; having this quiets a jest error
                            '--testRegex', 'test.bundle.js', 'build/test.bundle.js']);
                    });
                }
            }
        ]
    }, base)
];

