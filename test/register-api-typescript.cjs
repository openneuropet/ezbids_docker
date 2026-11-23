// Test-only in-memory transpilation: never overwrite JavaScript used by a live API.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const apiRoot = path.resolve(__dirname, '../api') + path.sep;
const original = Module._resolveFilename;
Module._resolveFilename = function (request, parent, ...rest) {
    if (parent && (request.startsWith('.') || path.isAbsolute(request))) {
        const candidate = path.resolve(path.dirname(parent.filename), request).replace(/\.js$/, '');
        if (candidate.startsWith(apiRoot) && fs.existsSync(candidate + '.ts')) return candidate + '.ts';
    }
    return original.call(this, request, parent, ...rest);
};
require.extensions['.ts'] = (module, filename) => {
    const result = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
        fileName: filename,
    });
    const readFile = fs.readFileSync;
    if (filename === path.join(apiRoot, 'auth.ts') && process.env.EZBIDS_TEST_KEY_DIR) {
        fs.readFileSync = function (file, ...args) {
            if ([path.join(apiRoot, 'ezbids.key'), path.join(apiRoot, 'ezbids.pub')].includes(String(file))) {
                file = path.join(process.env.EZBIDS_TEST_KEY_DIR, path.basename(file));
            }
            return readFile.call(this, file, ...args);
        };
    }
    try {
        module._compile(result.outputText, filename);
    } finally {
        fs.readFileSync = readFile;
    }
    if (filename === path.join(apiRoot, 'config.ts') && process.env.EZBIDS_TEST_WORKDIR) {
        module.exports.workdir = process.env.EZBIDS_TEST_WORKDIR;
        module.exports.multer = { dest: path.join(process.env.EZBIDS_TEST_WORKDIR, 'upload') };
    }
};
