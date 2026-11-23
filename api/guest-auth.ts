import { createHash, randomBytes, createPublicKey } from 'crypto';
import * as jwt from 'jsonwebtoken';
import { GuestSession, LegacyGuestKey, Session } from './models';

const digest = (value: string) => createHash('sha256').update(value).digest('hex');
export const guestLifetime = 30 * 24 * 60 * 60 * 1000;

export async function preserveGuestPublicKey(pem: string) {
    if (!/^-----BEGIN (RSA )?PUBLIC KEY-----/m.test(pem))
        throw new Error('Provide the current deployment public key, not a private key');
    const key = createPublicKey(pem);
    if (key.asymmetricKeyType !== 'rsa') throw new Error('Guest verification requires an RSA public key');
    const publicKey = key.export({ type: 'spki', format: 'pem' }).toString();
    const keyId = digest(publicKey);
    await LegacyGuestKey.updateOne({ keyId }, { $setOnInsert: { keyId, publicKey } }, { upsert: true });
    return keyId;
}

// Called before API readiness. Existing installations must import their OLD
// verification key before replacement; silently trusting a new image's key
// cannot recover guest cookies signed by the previous deployment.
export async function prepareGuestKeys(currentPublicKey: string) {
    if (await LegacyGuestKey.exists({})) return;
    if (await Session.exists({ ownerPrincipalId: /^local:guest:/ })) {
        throw new Error(
            'Import the previous deployment guest public key with preserve-guest-key before replacing the API'
        );
    }
    await preserveGuestPublicKey(currentPublicKey);
}

async function issue(guestId: string, expiresAt: Date, legacy = false) {
    const token = 'g1_' + randomBytes(32).toString('hex');
    await GuestSession.create({ tokenHash: digest(token), guestId, expiresAt, legacy });
    return { guestId, subject: `${legacy ? 'guest' : 'guest-v2'}:${guestId}`, replacement: { token, expiresAt } };
}

export async function resolveGuest(token: string) {
    if (/^g1_[a-f0-9]{64}$/.test(token)) {
        const session = await GuestSession.findOne({ tokenHash: digest(token), expiresAt: { $gt: new Date() } });
        return session
            ? {
                  guestId: session.guestId,
                  subject: `${session.legacy ? 'guest' : 'guest-v2'}:${session.guestId}`,
                  replacement: null,
              }
            : null;
    }
    if (!token || token.length > 8192) return null;
    const stored = await LegacyGuestKey.find({}).select('publicKey').lean();
    const keys = [...new Set(stored.map((entry) => entry.publicKey))];
    for (const key of keys) {
        let claims: jwt.JwtPayload;
        try {
            claims = jwt.verify(token, key, { algorithms: ['RS256'], audience: 'ezbids-guest' }) as jwt.JwtPayload;
        } catch {
            continue;
        }
        if (
            typeof claims.guestId !== 'string' ||
            !/^[a-f0-9]{32}$/.test(claims.guestId) ||
            !Number.isFinite(claims.exp)
        )
            return null;
        // Preserve both identity and original expiry; this is not a claim of
        // anonymous legacy uploads and does not extend an old cookie's lifetime.
        // Legacy signatures cannot authenticate the separate namespace used by
        // new opaque guests, even if a principal ID and an old image key leak.
        if (!(await Session.exists({ ownerPrincipalId: `local:guest:${claims.guestId}` }))) return null;
        return issue(claims.guestId, new Date(claims.exp * 1000), true);
    }
    return null;
}

export async function newGuest() {
    return issue(randomBytes(16).toString('hex'), new Date(Date.now() + guestLifetime));
}
