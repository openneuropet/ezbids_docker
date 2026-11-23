import * as fs from 'fs';
import * as path from 'path';

const badRequest = (message: string): Error => Object.assign(new Error(message), { status: 400 });
const missing = (error: any): boolean => error.code === 'ENOENT';

function inspectDirectory(directory: string): boolean {
    try {
        const stat = fs.lstatSync(directory);
        if (stat.isSymbolicLink() || !stat.isDirectory())
            throw badRequest('Upload directory must not be a symlink or file');
        return true;
    } catch (error) {
        if (missing(error)) return false;
        throw error;
    }
}

function inspectDestination(root: string, relative: string, create: boolean): string {
    if (!inspectDirectory(root) && create) fs.mkdirSync(root, { mode: 0o700 });
    const components = relative.split('/');
    let directory = root;
    for (const component of components.slice(0, -1)) {
        directory = path.join(directory, component);
        if (!inspectDirectory(directory) && create) fs.mkdirSync(directory, { mode: 0o700 });
    }
    const destination = path.join(root, ...components);
    try {
        const stat = fs.lstatSync(destination);
        if (stat.isSymbolicLink() || !stat.isFile()) throw badRequest('Upload destination must be a regular file');
    } catch (error) {
        if (!missing(error)) throw error;
    }
    if (create) {
        // Recheck the actual directory immediately before rename. Rename replaces
        // the directory entry rather than following a destination-file symlink.
        const realRoot = fs.realpathSync(root);
        const realParent = fs.realpathSync(path.dirname(destination));
        if (realRoot !== root || (realParent !== root && !realParent.startsWith(root + path.sep))) {
            throw badRequest('Upload directory escaped its session');
        }
    }
    return destination;
}

export function storeUploads(workdir: string, sessionId: string, files: any[], paths: unknown, mtimes: unknown) {
    const uploaded = Array.isArray(files) ? files : [];
    try {
        if (!/^[a-f0-9]{24}$/i.test(sessionId)) throw badRequest('Invalid session');
        const names = Array.isArray(paths) ? paths : paths === undefined ? [] : [paths];
        const times = Array.isArray(mtimes) ? mtimes : mtimes === undefined ? undefined : [mtimes];
        if (!uploaded.length || names.length !== uploaded.length || (times && times.length !== uploaded.length)) {
            throw badRequest('Upload file, path, and timestamp counts must match');
        }
        const root = path.join(fs.realpathSync(workdir), sessionId);
        const seen = new Set<string>();
        // Validate the entire batch before moving any file.
        const plans = uploaded.map((file, index) => {
            let relative = names[index];
            if (typeof relative !== 'string' || /[\\\x00-\x1f\x7f]/.test(relative) || /^[a-z]:/i.test(relative)) {
                throw badRequest('Invalid relative upload path');
            }
            if (relative.startsWith('./')) relative = relative.slice(2);
            if (relative.split('/').some((part) => !part || part === '.' || part === '..')) {
                throw badRequest('Upload paths must stay inside their session');
            }
            const destination = path.resolve(root, relative);
            if (!destination.startsWith(root + path.sep) || seen.has(destination))
                throw badRequest('Invalid or duplicate upload destination');
            seen.add(destination);
            const timestamp = times ? Number(times[index]) : undefined;
            if (
                times &&
                ((typeof times[index] !== 'string' && typeof times[index] !== 'number') ||
                    String(times[index]).trim() === '' ||
                    !Number.isFinite(timestamp) ||
                    !Number.isFinite(new Date(timestamp).getTime()))
            ) {
                throw badRequest('Invalid upload timestamp');
            }
            inspectDestination(root, relative, false);
            return { source: file.path, relative, timestamp };
        });
        for (const destination of seen) {
            let parent = path.dirname(destination);
            while (parent !== root) {
                if (seen.has(parent)) throw badRequest('A path cannot be both an uploaded file and directory');
                parent = path.dirname(parent);
            }
        }
        for (const plan of plans) {
            const destination = inspectDestination(root, plan.relative, true);
            fs.renameSync(plan.source, destination);
            if (plan.timestamp !== undefined) fs.utimesSync(destination, plan.timestamp / 1000, plan.timestamp / 1000);
        }
    } finally {
        // Multer has already accepted the body. Remove its temporary files even
        // when metadata/path validation rejects the request.
        for (const file of uploaded) {
            try {
                fs.unlinkSync(file.path);
            } catch (error) {
                if (!missing(error)) throw error;
            }
        }
    }
}
