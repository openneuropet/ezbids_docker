import { promises as dns } from 'dns';
import proxyaddr = require('proxy-addr');

const normalize = (ip: string): string => (ip.startsWith('::ffff:') ? ip.slice(7) : ip);

// Named proxies are resolved on the private deployment network. Never infer
// trust from a forwarding header or trust every address in a Docker subnet.
export function configureProxyTrust(app, addresses: string[] = [], names: string[] = [], lookup = dns.lookup) {
    const explicit = proxyaddr.compile(addresses);
    let resolved = new Set<string>();
    let expires = 0;
    let refreshing: Promise<void>;
    app.set('trust proxy', (ip: string) => explicit(ip) || resolved.has(normalize(ip)));
    app.use(async (_req, _res, next) => {
        if (!names.length) return next();
        try {
            if (Date.now() >= expires && !refreshing) {
                refreshing = Promise.all(
                    names.map(async (name) => {
                        try {
                            return await lookup(name, { all: true });
                        } catch {
                            return [];
                        }
                    })
                )
                    .then((groups) => {
                        resolved = new Set(
                            groups.reduce(
                                (all, group) => all.concat(group.map((entry) => normalize(entry.address))),
                                [] as string[]
                            )
                        );
                        expires = Date.now() + 5000;
                    })
                    .finally(() => {
                        refreshing = undefined;
                    });
            }
            if (refreshing) await refreshing;
            return next();
        } catch (error) {
            return next(error);
        }
    });
}
