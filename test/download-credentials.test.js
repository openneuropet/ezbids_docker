const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function component(relative, bindings, globals = {}) {
    const text = fs.readFileSync(path.resolve(__dirname, '../ui/src', relative), 'utf8');
    const script = text.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
    const code = ts.transpileModule(script, {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    const exports = {};
    vm.runInNewContext(code, {
        exports,
        module: { exports },
        console,
        ...globals,
        require: (name) => {
            if (name === 'vue') return { defineComponent: (definition) => definition };
            if (name === 'vuex') return { mapState: () => ({}) };
            if (name === 'element-plus') return { ElNotification: () => {} };
            if (name === './lib') return { hasAuth: () => false };
            if (name.endsWith('.vue')) return {};
            if (Object.prototype.hasOwnProperty.call(bindings, name)) {
                return name.endsWith('axios.instance') ? { default: bindings[name] } : bindings[name];
            }
            throw new Error(`Unexpected import ${name}`);
        },
    });
    return exports.default;
}

test('Finalize manifest and per-file fetches include credentials across UI/API ports', async () => {
    const requests = [],
        written = [];
    const directory = {
        getDirectoryHandle: async () => directory,
        getFileHandle: async () => ({
            createWritable: async () => ({
                write: async (bytes) => written.push(bytes),
                close: async () => {},
            }),
        }),
    };
    const definition = component(
        'Finalize.vue',
        { './axios.instance': { get: async () => ({ data: 'fixture-token' }) } },
        {
            window: { showDirectoryPicker: async () => directory },
            fetch: async (url, options) => {
                requests.push({ url, credentials: options?.credentials });
                return requests.length === 1
                    ? { ok: true, json: async () => ['sub-01/anat/image.nii'] }
                    : { ok: true, body: null, blob: async () => 'fixture bytes' };
            },
        }
    );
    await definition.methods.writeToExistingDataset.call({
        config: { apihost: 'http://localhost:8082' },
        session: { _id: 'fixture-session' },
        ezbids: { datasetDescription: { Name: 'fixture-dataset' } },
        writingDataset: false,
    });
    assert.equal(requests.length, 2);
    assert.ok(requests.every((request) => request.credentials === 'include'));
    assert.ok(requests.every((request) => request.url.startsWith('http://localhost:8082/download/fixture-session/')));
    assert.deepEqual(written, ['fixture bytes']);
});

test('Niivue receives downloaded bytes through the credential-aware client instead of fetching the URL', async () => {
    const requests = [],
        volumes = [],
        bytes = new ArrayBuffer(8);
    let viewer;
    class Niivue {
        constructor() {
            this.volumes = [];
            viewer = this;
        }
        async attachToCanvas() {}
        addVolume(volume) {
            this.volumes.push(volume);
        }
        removeVolume(volume) {
            this.volumes.splice(this.volumes.indexOf(volume), 1);
        }
        loadVolumes() {
            throw new Error('URL-based Niivue fetch omits cross-origin cookies');
        }
    }
    class NVImage {
        constructor(buffer, name) {
            volumes.push({ buffer, name });
        }
    }
    const definition = component('components/niivue.vue', {
        '@niivue/niivue': { Niivue, NVImage },
        '../axios.instance': {
            get: async (url, options) => {
                requests.push({ url, options });
                return { data: requests.length === 1 ? 'fixture-token' : bytes };
            },
        },
    });
    await definition.methods.load.call({
        config: { apihost: 'http://localhost:8082' },
        session: { _id: 'fixture-session' },
        path: 'anatomical.nii.gz',
        $refs: { canvas: {} },
        $nextTick: async () => {},
        open: false,
    });
    assert.equal(requests.length, 2);
    assert.equal(requests[1].options.responseType, 'arraybuffer');
    assert.equal(volumes[0].buffer, bytes);
    assert.equal(volumes[0].name, 'anatomical.nii.gz');
    assert.equal(viewer.volumes.length, 1);
});
