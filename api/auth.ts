import { Params, expressjwt } from 'express-jwt';
import * as fs from 'fs';
import * as jwt from 'jsonwebtoken';
import * as config from './config';
import { createHash, randomBytes, scrypt, timingSafeEqual } from 'crypto';
import { promisify } from 'util';
import { LoginSession, User } from './models';

const pubkey = config.authMode === 'brainlife' ? fs.readFileSync(__dirname + '/auth.pub', 'ascii').trim() : null;
const ezbidsPrivateKey = fs.readFileSync(`${__dirname}/ezbids.key`, 'ascii').trim();
const ezbidsPublicKey = fs.readFileSync(`${__dirname}/ezbids.pub`, 'ascii').trim();

export const validateWithJWTConfig = (options?: Params) => {
    if (config.authMode === 'local') return validateOptionalLocalSession;
    if (config.authMode === 'brainlife') {
        return expressjwt({
            secret: pubkey,
            algorithms: ['RS256'],
            ...options,
        });
    } else {
        return (req: any, res: any, next: any) => {
            req.auth = {
                sub: 0,
            };

            next();
        };
    }
};

export const verifyJWT = (jwtToVerify?: string): string | jwt.JwtPayload | undefined => {
    if (!jwtToVerify) return undefined;
    return jwt.verify(jwtToVerify, ezbidsPublicKey, { algorithms: ['RS256'] });
};

export const signJWT = (claims: { sessionId: string }, signInOpts?: jwt.SignOptions) => {
    return jwt.sign(claims, ezbidsPrivateKey, {
        algorithm: 'RS256',
        expiresIn: '600s',
        ...(signInOpts || {}),
    });
};

export const normalizeEmail = (email: unknown): string => (typeof email === 'string' ? email.trim().toLowerCase() : '');
const scryptAsync = promisify(scrypt);
export async function hashPassword(password: string): Promise<string> {
    const salt = randomBytes(16).toString('hex');
    const hash = (await scryptAsync(password, salt, 64)) as Buffer;
    return `scrypt$${salt}$${hash.toString('hex')}`;
}
export async function checkPassword(password: string, stored: string): Promise<boolean> {
    const [algorithm, salt, hex] = stored.split('$');
    if (algorithm !== 'scrypt' || !salt || !hex || hex.length !== 128) return false;
    const hash = (await scryptAsync(password, salt, 64)) as Buffer;
    return timingSafeEqual(hash, Buffer.from(hex, 'hex'));
}
export const cookieName = 'ezbids_login';
export const tokenHash = (token: string) => createHash('sha256').update(token).digest('hex');
export function readLoginToken(req, name = cookieName): string {
    const cookie = (req.headers.cookie || '')
        .split(';')
        .map((part: string) => part.trim())
        .find((part: string) => part.startsWith(`${name}=`));
    return cookie ? cookie.slice(name.length + 1) : '';
}
export const cookieOptions = { httpOnly: true, secure: config.secureCookies, sameSite: 'lax' as const, path: '/' };
export const publicUser = (user) => ({
    _id: String(user._id),
    email: user.email,
    displayName: user.displayName,
    role: user.role,
});
export async function startLogin(user, res) {
    const token = randomBytes(32).toString('hex');
    const maxAge = 7 * 24 * 60 * 60 * 1000;
    await LoginSession.create({
        tokenHash: tokenHash(token),
        userId: user._id,
        expiresAt: new Date(Date.now() + maxAge),
    });
    res.cookie(cookieName, token, { ...cookieOptions, maxAge });
    return res.json({ user: publicUser(user) });
}
async function findLocalUser(req) {
    const token = readLoginToken(req);
    if (!/^[a-f0-9]{64}$/.test(token)) return null;
    const session = await LoginSession.findOne({ tokenHash: tokenHash(token), expiresAt: { $gt: new Date() } });
    const user = session && (await User.findById(session.userId));
    return user && !user.disabled ? user : null;
}
export async function validateLocalSession(req, res, next) {
    try {
        const user = await findLocalUser(req);
        if (!user) return res.status(401).json({ message: 'Please log in' });
        req.auth = { sub: String(user._id) };
        req.localUser = user;
        return next();
    } catch (err) {
        next(err);
    }
}
// Guests can convert without an account. Their work remains private to the
// browser holding this signed cookie; it is never added to account history.
export async function validateOptionalLocalSession(req, res, next) {
    try {
        const user = await findLocalUser(req);
        if (user) {
            req.auth = { sub: String(user._id) };
            req.localUser = user;
            return next();
        }
        let guestId: string;
        try {
            const claims = jwt.verify(readLoginToken(req, 'ezbids_guest'), ezbidsPublicKey, {
                algorithms: ['RS256'],
                audience: 'ezbids-guest',
            }) as jwt.JwtPayload;
            if (typeof claims.guestId === 'string' && /^[a-f0-9]{32}$/.test(claims.guestId)) guestId = claims.guestId;
        } catch {
            /* Missing or expired guest cookies cannot grant access to existing work. */
        }
        if (!guestId) {
            if (req.method !== 'POST' || req.path !== '/session')
                return res.status(401).json({ message: 'Session access requires the original browser or account' });
            guestId = randomBytes(16).toString('hex');
            const maxAge = 30 * 24 * 60 * 60 * 1000;
            const token = jwt.sign({ guestId }, ezbidsPrivateKey, {
                algorithm: 'RS256',
                audience: 'ezbids-guest',
                expiresIn: '30d',
            });
            res.cookie('ezbids_guest', token, { ...cookieOptions, maxAge });
        }
        req.auth = { sub: `guest:${guestId}` };
        return next();
    } catch (err) {
        next(err);
    }
}
export const principalId = (req): string =>
    `${config.authMode === 'disabled' ? 'anonymous' : config.authMode}:${req.auth.sub}`;
