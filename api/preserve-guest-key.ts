#!/usr/bin/node
// Run against the existing database BEFORE replacing the old deployment image.
import * as fs from 'fs';
import * as models from './models';
import { preserveGuestPublicKey } from './guest-auth';

const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== '--public-key') {
    console.error('Usage: node preserve-guest-key.js --public-key /path/to/OLD/ezbids.pub');
    process.exit(2);
}
const publicKey = fs.readFileSync(args[1], 'utf8');
models.connect(async (error) => {
    if (error) throw error;
    try {
        const keyId = await preserveGuestPublicKey(publicKey);
        console.debug(`Preserved guest verification key fingerprint ${keyId}`);
        models.disconnect(() => process.exit(0));
    } catch (failure) {
        console.error((failure as Error).message);
        models.disconnect(() => process.exit(1));
    }
});
