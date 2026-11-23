require('./register-api-typescript.cjs');
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const express = require('express');
const jwt = require('jsonwebtoken');
const { storeUploads } = require('../api/upload-paths.ts');
const { configureProxyTrust } = require('../api/proxy-trust.ts');
const { createAuthAttemptLimiter } = require('../api/auth-attempts.ts');

const guestRows = new Map();
const keyRows = new Map();
let legacyUploads = false;
const legacySubjects = new Set();
const models = {
    User: { findOne: () => ({ select: async () => null }) },
    GuestSession: {
        create: async (row) => {
            guestRows.set(row.tokenHash, row);
        },
        findOne: async (query) => {
            const row = guestRows.get(query.tokenHash);
            return row && row.expiresAt > query.expiresAt.$gt ? row : null;
        },
    },
    LegacyGuestKey: {
        exists: async () => keyRows.size > 0,
        updateOne: async (query, update) => {
            if (!keyRows.has(query.keyId)) keyRows.set(query.keyId, update.$setOnInsert);
        },
        find: () => ({ select: () => ({ lean: async () => [...keyRows.values()] }) }),
    },
    Session: {
        exists: async (query) =>
            query.ownerPrincipalId instanceof RegExp ? legacyUploads : legacySubjects.has(query.ownerPrincipalId),
    },
};
const modelPath = require.resolve('../api/models.ts');
require.cache[modelPath] = { id: modelPath, filename: modelPath, loaded: true, exports: models };
const { newGuest, resolveGuest, prepareGuestKeys, preserveGuestPublicKey } = require('../api/guest-auth.ts');
const pair = () =>
    crypto.generateKeyPairSync('rsa', {
        modulusLength: 2048,
        publicKeyEncoding: { type: 'spki', format: 'pem' },
        privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    });
const originalKeys = pair();
const replacementKeys = pair();
const hashJobs = [];
let outstanding = 0,
    peak = 0;
const originalRead = fs.readFileSync;
const originalScrypt = crypto.scrypt;
let auth;
try {
    fs.readFileSync = function (filename, ...args) {
        if (String(filename).endsWith('/api/ezbids.key')) return originalKeys.privateKey;
        if (String(filename).endsWith('/api/ezbids.pub')) return originalKeys.publicKey;
        return originalRead.call(this, filename, ...args);
    };
    crypto.scrypt = (_password, _salt, length, callback) => {
        outstanding++;
        peak = Math.max(peak, outstanding);
        hashJobs.push((error) => {
            outstanding--;
            callback(error, Buffer.alloc(length));
        });
    };
    auth = require('../api/auth.ts');
} finally {
    fs.readFileSync = originalRead;
    crypto.scrypt = originalScrypt;
}
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function until(predicate) {
    for (let count = 0; count < 200; count++) {
        if (predicate()) return;
        await new Promise((resolve) => setTimeout(resolve, 5));
    }
    assert.fail('Fixture did not reach its expected state');
}
async function listen(t, handler) {
    const server = http.createServer(handler);
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    t.after(async () => {
        const stopped = new Promise((resolve) => server.close(resolve));
        server.closeAllConnections();
        await stopped;
    });
    return { server, url: `http://127.0.0.1:${server.address().port}` };
}

test('disposable database validation rejects production paths disguised by query strings', () => {
    const validate = require('./disposable-mongo.cjs');
    assert.equal(validate('mongodb://localhost:27017/ezbids_auth_test'), 'mongodb://localhost:27017/ezbids_auth_test');
    assert.equal(
        validate('mongodb://localhost/ezbids_auth_test?authSource=admin'),
        'mongodb://localhost/ezbids_auth_test?authSource=admin'
    );
    for (const uri of [
        'mongodb://localhost/ezbids_auth_preview',
        'mongodb://localhost/ezbids_auth_preview?appName=/ezbids_auth_test',
        'mongodb://localhost/ezbids_auth_test?dbName=production',
    ]) {
        assert.throws(() => validate(uri), /explicitly named/);
    }
});

test('disconnected requests retain slots until their actual password hashes settle', async (t) => {
    let closed = 0;
    const { url } = await listen(t, async (_req, res) => {
        res.on('close', () => closed++);
        try {
            await auth.hashPassword('disposable test password');
            res.end('done');
        } catch (error) {
            res.statusCode = error.status || 500;
            res.end();
        }
    });
    const clients = Array.from({ length: 4 }, () => {
        const request = http.get(url);
        request.on('error', () => {});
        return request;
    });
    await until(() => hashJobs.length === 4);
    clients.forEach((client) => client.destroy());
    await until(() => closed === 4);
    await assert.rejects(auth.hashPassword('cannot start a fifth hash'), { status: 429 });
    assert.equal(outstanding, 4);
    hashJobs.splice(0).forEach((finish) => finish());
    await tick();
    const next = auth.hashPassword('subsequent request works');
    assert.equal(hashJobs.length, 1);
    hashJobs.shift()();
    await next;
    assert.equal(outstanding, 0);
    assert.equal(peak, 4);
});

test('hash errors also release work slots', async () => {
    const failed = auth.hashPassword('failure');
    hashJobs.shift()(new Error('synthetic hash error'));
    await assert.rejects(failed, /synthetic hash error/);
    const retries = Array.from({ length: 4 }, () => auth.hashPassword('retry'));
    assert.equal(hashJobs.length, 4);
    hashJobs.splice(0).forEach((finish) => finish());
    await Promise.all(retries);
});

test('unknown-account login does exactly one bounded hash and recovers after saturation', async (t) => {
    const app = express();
    app.use(express.json());
    app.use('/auth', require('../api/auth.routes.ts'));
    app.use((error, _req, res, _next) => res.status(error.status || 500).json({ message: error.message }));
    const { url } = await listen(t, app);
    const login = () =>
        fetch(url + '/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'unknown@example.org', password: 'fixture password' }),
        });
    const pending = Array.from({ length: 4 }, login);
    await until(() => hashJobs.length === 4);
    assert.equal((await login()).status, 429);
    assert.equal(hashJobs.length, 4);
    hashJobs.splice(0).forEach((finish) => finish());
    for (const response of await Promise.all(pending)) assert.equal(response.status, 401);
    const next = login();
    await until(() => hashJobs.length === 1);
    hashJobs.shift()();
    assert.equal((await next).status, 401);
});

function uploadFixture(t) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ezbids-upload-regression-'));
    t.after(() => fs.rmSync(root, { recursive: true, force: true }));
    const own = '111111111111111111111111',
        victim = '222222222222222222222222';
    const victimDir = path.join(root, victim);
    fs.mkdirSync(victimDir);
    const victimFile = path.join(victimDir, 'protected.txt');
    fs.writeFileSync(victimFile, 'unchanged');
    let sequence = 0;
    const files = (count = 1) =>
        Array.from({ length: count }, () => {
            const file = path.join(root, `multer-${sequence++}`);
            fs.writeFileSync(file, 'uploaded');
            return { path: file };
        });
    return { root, own, victim, victimDir, victimFile, files };
}

test('nested uploads succeed and malformed multipart batches cannot escape their session', (t) => {
    const f = uploadFixture(t);
    storeUploads(f.root, f.own, f.files(), ['subject/anat/image.nii'], ['0']);
    assert.equal(fs.readFileSync(path.join(f.root, f.own, 'subject/anat/image.nii'), 'utf8'), 'uploaded');
    for (const relative of [
        `../${f.victim}/protected.txt`,
        `/tmp/outside`,
        `../${f.own}-sibling/file`,
        'a/../../outside',
        'a/../file',
        'C:\\outside\\file',
        'a\\..\\file',
        '',
        'a//file',
        'a\0file',
    ]) {
        const temporary = f.files();
        assert.throws(() => storeUploads(f.root, f.own, temporary, [relative], ['0']), { status: 400 }, relative);
        assert.ok(!fs.existsSync(temporary[0].path));
    }
    for (const [names, times] of [
        [[], ['0']],
        [['a', 'b'], ['0']],
        [[{}], ['0']],
        [['a'], ['NaN']],
    ]) {
        assert.throws(() => storeUploads(f.root, f.own, f.files(), names, times), { status: 400 });
    }
    assert.throws(
        () => storeUploads(f.root, f.own, f.files(2), ['valid', `../${f.victim}/protected.txt`], ['0', '0']),
        { status: 400 }
    );
    assert.ok(!fs.existsSync(path.join(f.root, f.own, 'valid')));
    assert.equal(fs.readFileSync(f.victimFile, 'utf8'), 'unchanged');
});

test('uploads reject directory/file symlinks and conflicting destinations', (t) => {
    const f = uploadFixture(t),
        ownDir = path.join(f.root, f.own);
    fs.mkdirSync(ownDir);
    fs.symlinkSync(f.victimDir, path.join(ownDir, 'link'));
    fs.symlinkSync(f.victimFile, path.join(ownDir, 'file-link'));
    for (const relative of ['link/protected.txt', 'file-link']) {
        assert.throws(() => storeUploads(f.root, f.own, f.files(), relative, '0'), { status: 400 });
    }
    assert.throws(() => storeUploads(f.root, f.own, f.files(2), ['same', 'same'], ['0', '0']), { status: 400 });
    assert.throws(() => storeUploads(f.root, f.own, f.files(2), ['parent', 'parent/file'], ['0', '0']), {
        status: 400,
    });
    assert.ok(!fs.existsSync(path.join(ownDir, 'parent')));
    fs.rmSync(ownDir, { recursive: true });
    fs.symlinkSync(f.victimDir, ownDir);
    assert.throws(() => storeUploads(f.root, f.own, f.files(), 'protected.txt', '0'), { status: 400 });
    assert.equal(fs.readFileSync(f.victimFile, 'utf8'), 'unchanged');
});

async function proxyFixture(t, names, lookup) {
    const app = express();
    configureProxyTrust(app, [], names, lookup);
    app.use('/auth', createAuthAttemptLimiter(2));
    app.post('/auth/login', (req, res) => res.json({ ip: req.ip }));
    return (await listen(t, app)).url;
}
const attempt = (url, forwarded) =>
    fetch(url + '/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Forwarded-For': forwarded },
        body: '{}',
    });

test('trusted nginx peers get separate client buckets and ignore spoofed earlier hops', async (t) => {
    const url = await proxyFixture(t, ['nginx'], async () => [{ address: '127.0.0.1', family: 4 }]);
    assert.equal((await attempt(url, '198.51.100.1')).status, 200);
    assert.equal((await attempt(url, '198.51.100.1')).status, 200);
    assert.equal((await attempt(url, '203.0.113.9, 198.51.100.1')).status, 429);
    const other = await attempt(url, '198.51.100.2');
    assert.equal(other.status, 200);
    assert.equal((await other.json()).ip, '198.51.100.2');
});

test('direct API peers cannot change their bucket with X-Forwarded-For', async (t) => {
    const url = await proxyFixture(t, [], undefined);
    const first = await attempt(url, '198.51.100.1');
    assert.equal((await first.json()).ip, '127.0.0.1');
    assert.equal((await attempt(url, '198.51.100.2')).status, 200);
    assert.equal((await attempt(url, '198.51.100.3')).status, 429);
});

test('failed proxy DNS resolution fails closed instead of trusting forwarded headers', async (t) => {
    const url = await proxyFixture(t, ['nginx'], async () => {
        throw new Error('DNS unavailable');
    });
    assert.equal((await (await attempt(url, '198.51.100.1')).json()).ip, '127.0.0.1');
});

test('new opaque guest cookies survive image signing-key replacement', async () => {
    guestRows.clear();
    keyRows.clear();
    legacyUploads = false;
    await prepareGuestKeys(originalKeys.publicKey);
    const identity = await newGuest();
    const restored = await resolveGuest(identity.replacement.token);
    assert.equal(restored.guestId, identity.guestId);
    assert.equal(restored.subject, `guest-v2:${identity.guestId}`);
    const forgedLegacy = jwt.sign({ guestId: identity.guestId }, originalKeys.privateKey, {
        algorithm: 'RS256',
        audience: 'ezbids-guest',
        expiresIn: '1h',
    });
    assert.equal(
        await resolveGuest(forgedLegacy),
        null,
        'legacy signatures must not authenticate opaque guest principals'
    );
    assert.ok(!JSON.stringify([...guestRows.values()]).includes(identity.replacement.token));
    await prepareGuestKeys(replacementKeys.publicKey);
    assert.equal(keyRows.size, 1, 'replacement must not overwrite the preserved verifier');
});

test('preserved legacy keys upgrade old guest cookies without changing identity or extending expiry', async () => {
    guestRows.clear();
    keyRows.clear();
    legacyUploads = true;
    await assert.rejects(prepareGuestKeys(replacementKeys.publicKey), /Import the previous deployment/);
    assert.equal(keyRows.size, 0);
    await preserveGuestPublicKey(originalKeys.publicKey);
    await prepareGuestKeys(replacementKeys.publicKey);
    legacySubjects.add('local:guest:' + 'a'.repeat(32));
    const token = jwt.sign({ guestId: 'a'.repeat(32) }, originalKeys.privateKey, {
        algorithm: 'RS256',
        audience: 'ezbids-guest',
        expiresIn: '2h',
    });
    const upgraded = await resolveGuest(token);
    assert.equal(upgraded.guestId, 'a'.repeat(32));
    assert.match(upgraded.replacement.token, /^g1_/);
    assert.equal(upgraded.replacement.expiresAt.getTime(), jwt.decode(token).exp * 1000);
    assert.equal((await resolveGuest(upgraded.replacement.token)).guestId, upgraded.guestId);
    assert.equal(await resolveGuest(token.slice(0, -5) + 'badxx'), null);
    assert.ok(!JSON.stringify([...keyRows.values()]).includes('PRIVATE KEY'));
    await assert.rejects(preserveGuestPublicKey(originalKeys.privateKey), /not a private key/);
});
