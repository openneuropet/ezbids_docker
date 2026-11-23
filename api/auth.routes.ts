import * as express from 'express';
import * as config from './config';
import { User, LoginSession } from './models';
import {
    normalizeEmail,
    hashPassword,
    checkPassword,
    startLogin,
    validateLocalSession,
    publicUser,
    cookieName,
    cookieOptions,
    readLoginToken,
    tokenHash,
} from './auth';

const router = express.Router();
router.get('/config', (_req, res) =>
    res.json({ mode: config.authMode, registrationEnabled: config.registrationEnabled })
);
router.use((_req, res, next) => (config.authMode === 'local' ? next() : res.sendStatus(404)));

// Bound password hashing work and repeated login attempts, without storing credentials.
let hashingRequests = 0;
const attempts = new Map<string, { count: number; until: number }>();
router.use((req, res, next) => {
    if (req.method !== 'POST' || !['/login', '/register'].includes(req.path)) return next();
    if (!req.is('application/json')) return res.status(415).json({ message: 'JSON is required' });
    const now = Date.now();
    for (const [key, value] of attempts) if (value.until <= now) attempts.delete(key);
    const key = req.ip;
    const entry = attempts.get(key) || { count: 0, until: now + 15 * 60 * 1000 };
    if (entry.count >= 30 || (!attempts.has(key) && attempts.size >= 10000)) {
        return res.status(429).json({ message: 'Too many attempts. Please try again later.' });
    }
    if (hashingRequests >= 4) return res.status(429).json({ message: 'Please try again shortly' });
    hashingRequests++;
    res.once('finish', () => {
        hashingRequests--;
    });
    entry.count++;
    attempts.set(key, entry);
    next();
});
router.post('/register', async (req, res, next) => {
    if (!config.registrationEnabled) return res.status(403).json({ message: 'Registration is disabled' });
    const email = normalizeEmail(req.body.email);
    const { displayName, password } = req.body;
    if (
        !/^\S+@\S+\.\S+$/.test(email) ||
        email.length > 254 ||
        typeof displayName !== 'string' ||
        !displayName.trim() ||
        displayName.length > 100 ||
        typeof password !== 'string' ||
        password.length < 12 ||
        password.length > 1024
    ) {
        return res.status(400).json({ message: 'Provide a name, valid email, and password of 12–1024 characters' });
    }
    try {
        const user = await User.create({
            email,
            displayName: displayName.trim(),
            passwordHash: await hashPassword(password),
            role: 'user',
        });
        res.status(201);
        await startLogin(user, res);
    } catch (err) {
        if (err.code === 11000) return res.status(409).json({ message: 'An account with that email already exists' });
        next(err);
    }
});
// Use a dummy hash for unknown accounts so that the expensive work is comparable.
let dummyHash: Promise<string>;
router.post('/login', async (req, res, next) => {
    const email = normalizeEmail(req.body.email);
    const password = req.body.password;
    if (!email || typeof password !== 'string' || password.length > 1024)
        return res.status(401).json({ message: 'Email or password is incorrect' });
    try {
        const user = await User.findOne({ email }).select('+passwordHash');
        if (!dummyHash) dummyHash = hashPassword('invalid-account-placeholder');
        const valid = await checkPassword(password, user?.passwordHash || (await dummyHash));
        if (!valid || !user || user.disabled)
            return res.status(401).json({ message: 'Email or password is incorrect' });
        await startLogin(user, res);
    } catch (err) {
        next(err);
    }
});
router.get('/me', validateLocalSession, (req: any, res) => res.json({ user: publicUser(req.localUser) }));
router.post('/logout', async (req, res, next) => {
    try {
        await LoginSession.deleteOne({ tokenHash: tokenHash(readLoginToken(req)) });
        res.clearCookie(cookieName, cookieOptions);
        res.sendStatus(204);
    } catch (err) {
        next(err);
    }
});
export = router;
