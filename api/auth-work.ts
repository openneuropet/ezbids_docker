// Limit the work itself: disconnecting a response must neither leak a slot nor
// release it while the password hash is still consuming resources.
export function createWorkLimiter(maximum: number) {
    let active = 0;
    return async function run<T>(work: () => Promise<T>): Promise<T> {
        if (active >= maximum) {
            const error = new Error('Please try again shortly');
            Object.assign(error, { status: 429 });
            throw error;
        }
        active++;
        try {
            return await work();
        } finally {
            active--;
        }
    };
}
