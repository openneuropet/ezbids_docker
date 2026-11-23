// Identity comes from Express's explicitly configured proxy policy, never from
// a client-supplied forwarding header read directly by this limiter.
export function createAuthAttemptLimiter(maximum = 30, windowMs = 15 * 60 * 1000) {
    const attempts = new Map<string, { count: number; until: number }>();
    return (req, res, next) => {
        if (req.method !== 'POST' || !['/login', '/register'].includes(req.path)) return next();
        if (!req.is('application/json')) return res.status(415).json({ message: 'JSON is required' });
        const now = Date.now();
        for (const [key, value] of attempts) if (value.until <= now) attempts.delete(key);
        const key = req.ip;
        const entry = attempts.get(key) || { count: 0, until: now + windowMs };
        if (entry.count >= maximum || (!attempts.has(key) && attempts.size >= 10000)) {
            return res.status(429).json({ message: 'Too many attempts. Please try again later.' });
        }
        entry.count++;
        attempts.set(key, entry);
        return next();
    };
}
