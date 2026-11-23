#!/usr/bin/node

import * as readline from 'readline';
import { Writable } from 'stream';
import { hashPassword, normalizeEmail } from './auth';
import * as models from './models';

const ask = (rl: readline.Interface, prompt: string): Promise<string> =>
    new Promise((resolve) => rl.question(prompt, resolve));

class MutedOutput extends Writable {
    muted = false;

    _write(chunk: any, _encoding: BufferEncoding, callback: (error?: Error | null) => void) {
        if (!this.muted) process.stdout.write(chunk);
        callback();
    }
}

const main = () =>
    models.connect(async (connectionError) => {
        if (connectionError) throw connectionError;
        const output = new MutedOutput();
        const rl = readline.createInterface({ input: process.stdin, output, terminal: Boolean(process.stdin.isTTY) });
        try {
            const email = normalizeEmail(process.env.EZBIDS_ADMIN_EMAIL || (await ask(rl, 'Admin email: ')));
            const displayName = String(
                process.env.EZBIDS_ADMIN_DISPLAY_NAME || (await ask(rl, 'Display name: ')) || 'Administrator'
            ).trim();
            let password = process.env.EZBIDS_ADMIN_PASSWORD;
            if (!password) {
                process.stdout.write('Password (12+ characters): ');
                output.muted = true;
                password = await ask(rl, '');
                output.muted = false;
                process.stdout.write('\n');
            }
            if (!/^\S+@\S+\.\S+$/.test(email)) throw new Error('A valid email address is required');
            if (password.length < 12) throw new Error('Password must be at least 12 characters');
            if (await models.User.exists({ email })) throw new Error(`Account already exists: ${email}`);
            const user = await models.User.create({
                email,
                displayName,
                passwordHash: await hashPassword(password),
                role: 'admin',
            });
            console.debug(`Created local administrator ${user.email}`);
            models.disconnect(() => process.exit(0));
        } catch (err) {
            console.error((err as Error).message);
            models.disconnect(() => process.exit(1));
        } finally {
            rl.close();
        }
    });

main();
