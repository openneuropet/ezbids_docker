const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function metadataFormMethods() {
    const filename = path.resolve(__dirname, '../ui/src/components/modalityForm.vue');
    const script = fs.readFileSync(filename, 'utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
    const code = ts.transpileModule(script, {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    const exports = {};
    vm.runInNewContext(code, {
        exports,
        module: { exports },
        require: (name) => {
            if (name === 'vue') return { defineComponent: (definition) => definition };
            if (name === 'element-plus' || name.endsWith('.yaml')) return {};
            throw new Error(`Unexpected import ${name}`);
        },
    });
    return exports.default.methods;
}

const methods = metadataFormMethods();

function saveMetadata(formData, definitions) {
    const original = { Manufacturer: 'fixture scanner', ExistingField: 'preserved' };
    const selected = { series_idx: 0, items: [{ name: 'json', sidecar_json: JSON.stringify(original) }] };
    const other = { series_idx: 1, items: [{ name: 'json', sidecar_json: JSON.stringify(original) }] };
    methods.createJSONOutput.call({
        formData,
        fields: { required: definitions },
        ss: { series_idx: 0 },
        ezbids: { objects: [selected, other] },
        parseArrayValues: methods.parseArrayValues,
    });
    assert.deepEqual(JSON.parse(other.items[0].sidecar_json), original);
    return JSON.parse(selected.items[0].sidecar_json);
}

test('PET string-array edits save JSON arrays in the selected series sidecar', () => {
    const metadata = saveMetadata(
        { ReconMethodParameterLabels: 'none', ReconFilterType: 'rectangle, gaussian' },
        ['ReconMethodParameterLabels', 'ReconFilterType'].map((field) => ({
            field,
            details: { type: 'array', items: { type: 'string' } },
        }))
    );
    assert.deepEqual(metadata.ReconMethodParameterLabels, ['none']);
    assert.deepEqual(metadata.ReconFilterType, ['rectangle', 'gaussian']);
    assert.equal(metadata.ExistingField, 'preserved');
});

test('PET numeric arrays and false boolean metadata retain their JSON types', () => {
    const metadata = saveMetadata(
        { FrameTimesStart: '0, 30.5', FrameDuration: [30.5, 60], ImageDecayCorrected: false },
        [
            ...['FrameTimesStart', 'FrameDuration'].map((field) => ({
                field,
                details: { type: 'array', items: { type: 'number' } },
            })),
            { field: 'ImageDecayCorrected', details: { type: 'boolean' } },
        ]
    );
    assert.deepEqual(metadata.FrameTimesStart, [0, 30.5]);
    assert.deepEqual(metadata.FrameDuration, [30.5, 60]);
    assert.equal(metadata.ImageDecayCorrected, false);
});

test('existing string arrays keep their entries when the metadata dialog saves', () => {
    const metadata = saveMetadata({ ReconMethodParameterLabels: ['iterations', 'label, with comma'] }, [
        { field: 'ReconMethodParameterLabels', details: { type: 'array', items: { type: 'string' } } },
    ]);
    assert.deepEqual(metadata.ReconMethodParameterLabels, ['iterations', 'label, with comma']);
});

test('switching a PET field from number to string removes its obsolete numeric rule', () => {
    const item = {
        field: 'InjectedMass',
        details: { type: 'number', anyOf: [{ type: 'number' }, { type: 'string', enum: ['n/a'] }] },
    };
    const form = {
        ...methods,
        fields: { required: [item], recommended: [], optional: [], conditional: [] },
        formData: { InjectedMass: 'n/a' },
    };
    form.rules = form.generateValidationRules(form.fields);
    assert.ok(form.rules.InjectedMass.some((rule) => rule.validator));
    form.updateDetailsType(item, 'string');
    const errors = [];
    for (const rule of form.rules.InjectedMass) {
        if (rule.validator) rule.validator(rule, 'n/a', (error) => error && errors.push(error.message));
    }
    assert.deepEqual(errors, []);
    assert.ok(form.rules.InjectedMass.some((rule) => rule.required));
    const metadata = saveMetadata({ InjectedMass: 'n/a' }, [item]);
    assert.equal(metadata.InjectedMass, 'n/a');
});
