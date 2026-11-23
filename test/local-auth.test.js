const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs/promises');
const mongoose = require('mongoose');

// This suite only runs against an explicitly selected disposable database.
const mongoUrl = process.env.EZBIDS_TEST_MONGO_URL;
if (!mongoUrl) {
    test('local authentication integration (set EZBIDS_TEST_MONGO_URL to run)', { skip: true }, () => {});
} else {
    if (!mongoUrl.endsWith('/ezbids_auth_test')) throw new Error('Test database must be named ezbids_auth_test');
    const base = 'http://127.0.0.1:18082';
    process.env.MONGO_CONNECTION_STRING = mongoUrl;
    delete process.env.EZBIDS_AUTH_MODE;
    process.env.BRAINLIFE_AUTHENTICATION = 'false';
    const models = require('../api/models');
    let server;
    let serverOutput = '';
    const files = [];
    const password = 'a long test password 123';
    let alice, bob, aliceSession, bobSession;
    async function request(path, { method = 'GET', cookie, body, headers = {} } = {}) {
        return fetch(base + path, {
            method,
            headers: {
                ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
                ...(cookie ? { Cookie: cookie } : {}),
                ...headers,
            },
            ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        });
    }
    const cookieOf = (res) => res.headers.get('set-cookie').split(';')[0];
    async function register(email) {
        const response = await request('/auth/register', {
            method: 'POST',
            body: { email, displayName: 'Test user', password, role: 'admin' },
        });
        assert.equal(response.status, 201);
        const data = await response.json();
        assert.equal(data.user.role, 'user');
        assert.equal(data.user.passwordHash, undefined);
        assert.match(response.headers.get('set-cookie'), /HttpOnly/);
        assert.match(response.headers.get('set-cookie'), /SameSite=Lax/);
        return { cookie: cookieOf(response), user: data.user };
    }
    before(async () => {
        await new Promise((resolve, reject) => models.connect((err) => (err ? reject(err) : resolve())));
        await Promise.all([
            models.User.deleteMany({}),
            models.LoginSession.deleteMany({}),
            models.Session.deleteMany({}),
        ]);
        server = spawn(process.execPath, ['api/ezbids.js'], {
            env: { ...process.env, PORT: '18082', HOST: '127.0.0.1', EZBIDS_REGISTRATION_ENABLED: 'true' },
        });
        server.stdout.on('data', (data) => {
            serverOutput += data;
        });
        server.stderr.on('data', (data) => {
            serverOutput += data;
        });
        for (let i = 0; i < 100; i++) {
            try {
                if ((await request('/health')).ok) return;
            } catch {}
            if (server.exitCode !== null) throw new Error(serverOutput);
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        throw new Error('API did not start: ' + serverOutput);
    });
    after(async () => {
        if (server && server.exitCode === null) {
            const exited = once(server, 'exit');
            server.kill();
            await exited;
        }
        for (const directory of files) await fs.rm(directory, { recursive: true, force: true });
        await mongoose.connection.dropDatabase();
        await mongoose.disconnect();
    });
    test('runtime configuration enables local registration', async () => {
        assert.deepEqual(await (await request('/auth/config')).json(), { mode: 'local', registrationEnabled: true });
    });
    test('guests cannot browse account history or open sessions without the original browser', async () => {
        for (const path of ['/sessions', '/session/000000000000000000000001', '/auth/me']) {
            assert.equal((await request(path)).status, 401);
        }
        const created = await request('/session', { method: 'POST', body: {} });
        assert.equal(created.status, 200);
        const guestCookie = cookieOf(created);
        assert.match(guestCookie, /^ezbids_guest=/);
        const guestSession = await created.json();
        assert.match(guestSession.ownerPrincipalId, /^local:guest:/);
        assert.equal((await request(`/session/${guestSession._id}`, { cookie: guestCookie })).status, 200);
        assert.equal((await request('/sessions', { cookie: guestCookie })).status, 401);
        const second = await request('/session', { method: 'POST', body: {} });
        assert.equal((await request(`/session/${guestSession._id}`, { cookie: cookieOf(second) })).status, 404);
        assert.equal((await request(`/session/${guestSession._id}`, { cookie: 'ezbids_guest=forged' })).status, 401);
        const repeated = await (await request('/session', { method: 'POST', cookie: guestCookie, body: {} })).json();
        assert.equal(repeated.ownerPrincipalId, guestSession.ownerPrincipalId);
        const directory = `/tmp/${guestSession._id}`;
        files.push(directory);
        await fs.mkdir(directory, { recursive: true });
        await fs.writeFile(`${directory}/guest.txt`, 'private guest file');
        const token = await (await request(`/download/${guestSession._id}/token`, { cookie: guestCookie })).text();
        assert.equal(
            await (
                await request(`/download/${guestSession._id}/guest.txt?token=${token}`, { cookie: guestCookie })
            ).text(),
            'private guest file'
        );
        assert.equal(
            (await request(`/download/${guestSession._id}/guest.txt?token=${token}`, { cookie: cookieOf(second) }))
                .status,
            404
        );
    });
    test('registration validates inputs, normalizes emails and never grants requested admin privileges', async () => {
        assert.equal(
            (await request('/auth/register', { method: 'POST', body: { email: {}, password: 'short' } })).status,
            400
        );
        alice = await register(' Alice@Example.org ');
        bob = await register('bob@example.org');
        assert.equal(alice.user.email, 'alice@example.org');
        const guest = await (await request('/session', { method: 'POST', body: {} })).json();
        assert.equal((await request(`/session/${guest._id}`, { cookie: alice.cookie })).status, 404);
        const user = await models.User.findById(alice.user._id).select('+passwordHash');
        assert.match(user.passwordHash, /^scrypt\$/);
        assert.ok(!user.passwordHash.includes(password));
        const duplicate = await request('/auth/register', {
            method: 'POST',
            body: { email: 'ALICE@example.org', displayName: 'Duplicate', password },
        });
        assert.equal(duplicate.status, 409);
    });
    test('login rejects wrong credentials and restores the same account', async () => {
        assert.equal(
            (
                await request('/auth/login', {
                    method: 'POST',
                    body: { email: 'alice@example.org', password: 'incorrect' },
                })
            ).status,
            401
        );
        assert.equal(
            (await request('/auth/login', { method: 'POST', body: { email: { $ne: null }, password } })).status,
            401
        );
        const res = await request('/auth/login', { method: 'POST', body: { email: 'ALICE@example.org', password } });
        assert.equal(res.status, 200);
        assert.equal((await res.json()).user._id, alice.user._id);
        assert.equal((await (await request('/auth/me', { cookie: cookieOf(res) })).json()).user._id, alice.user._id);
    });
    test('session creation assigns ownership server-side and history is private', async () => {
        aliceSession = await (
            await request('/session', {
                method: 'POST',
                cookie: alice.cookie,
                body: { ownerPrincipalId: `local:${bob.user._id}`, ownerId: 0, allowedUsers: [0], status: 'finished' },
            })
        ).json();
        bobSession = await (await request('/session', { method: 'POST', cookie: bob.cookie, body: {} })).json();
        assert.equal(aliceSession.ownerPrincipalId, `local:${alice.user._id}`);
        assert.equal(aliceSession.status, 'created');
        assert.deepEqual(aliceSession.allowedUsers, []);
        assert.equal(aliceSession.request_headers.cookie, undefined);
        for (const [account, session] of [
            [alice, aliceSession],
            [bob, bobSession],
        ]) {
            const history = await (await request('/sessions', { cookie: account.cookie })).json();
            assert.deepEqual(
                history.map((row) => row._id),
                [session._id]
            );
            assert.equal((await request(`/session/${session._id}`, { cookie: account.cookie })).status, 200);
        }
        const login = await request('/auth/login', { method: 'POST', body: { email: alice.user.email, password } });
        const history = await (await request('/sessions', { cookie: cookieOf(login) })).json();
        assert.equal(history[0]._id, aliceSession._id);
    });
    test('another user cannot read, modify, upload to, or mint download tokens for a known session ID', async () => {
        const id = aliceSession._id;
        for (const [method, path] of [
            ['GET', `/session/${id}`],
            ['PATCH', `/session/${id}`],
            ['POST', `/session/${id}/finalize`],
            ['POST', `/session/${id}/deface`],
            ['POST', `/session/${id}/canceldeface`],
            ['POST', `/session/${id}/resetdeface`],
            ['GET', `/session/${id}/updated`],
            ['POST', `/upload-multi/${id}`],
            ['PATCH', `/session/uploaded/${id}`],
            ['GET', `/download/${id}/token`],
        ]) {
            const response = await request(path, {
                method,
                cookie: bob.cookie,
                ...(method === 'GET' ? {} : { body: {} }),
            });
            assert.equal(response.status, 404, `${method} ${path}`);
        }
        assert.equal(
            (await request(`/session/${id}`, { method: 'PATCH', cookie: alice.cookie, body: { allowedUsers: [0] } }))
                .status,
            403
        );
        assert.equal((await request('/session/not-an-id', { cookie: alice.cookie })).status, 400);
    });
    test('legacy anonymous sessions stay private until assigned by an operator', async () => {
        const legacy = await models.Session.create({ ownerId: 0, status: 'created' });
        assert.equal((await request(`/session/${legacy._id}`, { cookie: alice.cookie })).status, 404);
        assert.equal((await request(`/session/${legacy._id}`, { cookie: bob.cookie })).status, 404);
        const assigned = spawn(process.execPath, [
            'api/assign-legacy-sessions.js',
            '--email',
            alice.user.email,
            String(legacy._id),
        ]);
        assert.equal((await once(assigned, 'exit'))[0], 0);
        assert.equal((await request(`/session/${legacy._id}`, { cookie: alice.cookie })).status, 200);
        assert.equal((await request(`/session/${legacy._id}`, { cookie: bob.cookie })).status, 404);
    });
    test('downloads require the owner login and a token bound to the requested session', async () => {
        const directory = `/tmp/${aliceSession._id}`;
        files.push(directory);
        await fs.mkdir(directory, { recursive: true });
        await fs.writeFile(`${directory}/test.txt`, 'private session file');
        const token = await (await request(`/download/${aliceSession._id}/token`, { cookie: alice.cookie })).text();
        const path = `/download/${aliceSession._id}/test.txt?token=${token}`;
        assert.equal(await (await request(path, { cookie: alice.cookie })).text(), 'private session file');
        assert.equal((await request(path, { cookie: bob.cookie })).status, 404);
        assert.equal((await request(path)).status, 401);
        assert.equal(
            (await request(`/download/${bobSession._id}/test.txt?token=${token}`, { cookie: bob.cookie })).status,
            401
        );
    });
    test('untrusted browser origins cannot register or access account data', async () => {
        assert.equal(
            (await request('/auth/register', { method: 'POST', headers: { Origin: 'https://evil.example' }, body: {} }))
                .status,
            403
        );
        assert.equal(
            (await request('/sessions', { cookie: alice.cookie, headers: { Origin: 'https://evil.example' } })).status,
            403
        );
        const response = await request('/auth/me', {
            cookie: alice.cookie,
            headers: { Origin: 'http://localhost:3000' },
        });
        assert.equal(response.headers.get('access-control-allow-origin'), 'http://localhost:3000');
        assert.equal(response.headers.get('access-control-allow-credentials'), 'true');
    });
    test('history pagination returns only the owner’s sessions', async () => {
        const seeded = await models.Session.insertMany(
            Array.from({ length: 55 }, () => ({ ownerPrincipalId: `local:${alice.user._id}`, status: 'created' }))
        );
        try {
            const first = await (await request('/sessions', { cookie: alice.cookie })).json();
            assert.equal(first.length, 50);
            const second = await (
                await request(`/sessions?before=${first.at(-1)._id}`, { cookie: alice.cookie })
            ).json();
            assert.equal(second.length, 7);
            const ids = [...first, ...second].map((session) => session._id);
            assert.equal(new Set(ids).size, 57);
            assert.ok(!ids.includes(bobSession._id));
            assert.equal((await request('/sessions?before=invalid', { cookie: alice.cookie })).status, 400);
        } finally {
            await models.Session.deleteMany({ _id: { $in: seeded.map((session) => session._id) } });
        }
    });
    test('expired sessions, disabled accounts, and logout revoke access', async () => {
        const { tokenHash } = require('../api/auth');
        await models.LoginSession.updateOne(
            { tokenHash: tokenHash(bob.cookie.split('=')[1]) },
            { expiresAt: new Date(0) }
        );
        assert.equal((await request('/sessions', { cookie: bob.cookie })).status, 401);
        await models.User.updateOne({ _id: alice.user._id }, { disabled: true });
        assert.equal((await request('/sessions', { cookie: alice.cookie })).status, 401);
        assert.equal(
            (await request('/auth/login', { method: 'POST', body: { email: alice.user.email, password } })).status,
            401
        );
        await models.User.updateOne({ _id: alice.user._id }, { disabled: false });
        assert.equal((await request('/auth/logout', { method: 'POST', cookie: alice.cookie })).status, 204);
        assert.equal((await request('/sessions', { cookie: alice.cookie })).status, 401);
    });
    test('registration can be disabled while existing users can log in with secure cookies', async () => {
        const restricted = spawn(process.execPath, ['api/ezbids.js'], {
            env: {
                ...process.env,
                PORT: '18083',
                HOST: '127.0.0.1',
                EZBIDS_REGISTRATION_ENABLED: 'false',
                EZBIDS_SECURE_COOKIES: 'true',
            },
        });
        restricted.stdout.resume();
        restricted.stderr.resume();
        try {
            let ready = false;
            for (let i = 0; i < 100; i++) {
                try {
                    if ((await fetch('http://127.0.0.1:18083/health')).ok) {
                        ready = true;
                        break;
                    }
                } catch {}
                await new Promise((resolve) => setTimeout(resolve, 100));
            }
            assert.ok(ready);
            assert.equal((await (await fetch('http://127.0.0.1:18083/auth/config')).json()).registrationEnabled, false);
            assert.equal(
                (
                    await fetch('http://127.0.0.1:18083/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{}',
                    })
                ).status,
                403
            );
            const login = await fetch('http://127.0.0.1:18083/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: alice.user.email, password }),
            });
            assert.equal(login.status, 200);
            assert.match(login.headers.get('set-cookie'), /Secure/);
        } finally {
            const exited = once(restricted, 'exit');
            restricted.kill();
            await exited;
        }
    });
    test('repeated authentication attempts are rate limited', async () => {
        let response;
        for (let i = 0; i < 31; i++) response = await request('/auth/login', { method: 'POST', body: {} });
        assert.equal(response.status, 429);
    });
}
