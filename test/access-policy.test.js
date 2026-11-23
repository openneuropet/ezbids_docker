const test = require('node:test');
const assert = require('node:assert/strict');
const { userCanAccessSession } = require('../api/access-policy');

test('disabled mode preserves anonymous session access', () => {
    assert.equal(userCanAccessSession('disabled', 'anonymous:0', 0, {}, true), true);
});

test('local mode permits only the creating principal', () => {
    const session = {
        ownerPrincipalId: 'local:user-a',
        allowedUsers: [2],
    };

    assert.equal(userCanAccessSession('local', 'local:user-a', 'user-a', session, true), true);
    assert.equal(userCanAccessSession('local', 'local:user-b', 'user-b', session, false), false);
});

test('brainlife mode preserves owner and explicit sharing behavior', () => {
    const legacySession = { ownerId: 1, allowedUsers: [2] };
    const principalSession = { ownerPrincipalId: 'brainlife:1', allowedUsers: [2] };

    assert.equal(userCanAccessSession('brainlife', 'brainlife:1', 1, legacySession, true), true);
    assert.equal(userCanAccessSession('brainlife', 'brainlife:1', 1, principalSession, true), true);
    assert.equal(userCanAccessSession('brainlife', 'brainlife:2', 2, legacySession, false), true);
    assert.equal(userCanAccessSession('brainlife', 'brainlife:2', 2, legacySession, true), false);
    assert.equal(userCanAccessSession('brainlife', 'brainlife:3', 3, legacySession, false), false);
});

test('authentication defaults to local unless Brainlife is enabled; explicit modes override defaults', () => {
    const { spawnSync } = require('node:child_process');
    const configPath = require.resolve('../api/config');
    for (const [brainlife, override, expected] of [
        [undefined, undefined, 'local'],
        ['false', undefined, 'local'],
        ['true', undefined, 'brainlife'],
        ['false', '', 'local'],
        ['false', 'disabled', 'disabled'],
        ['true', 'local', 'local'],
    ]) {
        const env = { ...process.env };
        delete env.BRAINLIFE_AUTHENTICATION;
        delete env.EZBIDS_AUTH_MODE;
        delete env.EZBIDS_REGISTRATION_ENABLED;
        if (brainlife !== undefined) env.BRAINLIFE_AUTHENTICATION = brainlife;
        if (override !== undefined) env.EZBIDS_AUTH_MODE = override;
        const result = spawnSync(
            process.execPath,
            [
                '--require',
                require.resolve('./register-api-typescript.cjs'),
                '-e',
                `const config = require(${JSON.stringify(configPath)}); console.log(JSON.stringify({ mode: config.authMode, registration: config.registrationEnabled }));`,
            ],
            { env, encoding: 'utf8' }
        );
        assert.equal(result.status, 0, result.stderr);
        assert.deepEqual(JSON.parse(result.stdout), { mode: expected, registration: expected === 'local' });
    }
});
