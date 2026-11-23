#!/usr/bin/node

import { Types } from 'mongoose';
import { normalizeEmail } from './auth';
import * as models from './models';

const args = process.argv.slice(2);
const emailIndex = args.indexOf('--email');
const email = emailIndex >= 0 ? normalizeEmail(args[emailIndex + 1]) : '';
const sessionIds = [
    ...new Set(args.filter((arg, index) => emailIndex < 0 || (index !== emailIndex && index !== emailIndex + 1))),
];

if (!email || sessionIds.length === 0 || sessionIds.some((id) => !Types.ObjectId.isValid(id))) {
    console.error('Usage: npm run assign-legacy-sessions -- --email user@example.org SESSION_ID [SESSION_ID ...]');
    process.exit(2);
}

models.connect(async (connectionError) => {
    if (connectionError) throw connectionError;
    try {
        const user = await models.User.findOne({ email });
        if (!user) throw new Error(`Local account not found: ${email}`);
        const legacySessionFilter = {
            _id: { $in: sessionIds.map((id) => new Types.ObjectId(id)) },
            $and: [
                {
                    $or: [
                        { ownerPrincipalId: 'anonymous:0' },
                        { ownerPrincipalId: { $exists: false } },
                        { ownerPrincipalId: null },
                    ],
                },
                { $or: [{ ownerId: 0 }, { ownerId: { $exists: false } }, { ownerId: null }] },
            ],
        };
        const eligibleCount = await models.Session.countDocuments(legacySessionFilter);
        if (eligibleCount !== sessionIds.length) {
            throw new Error(
                `${eligibleCount}/${sessionIds.length} sessions are eligible. No sessions were changed; check that every ID exists and is legacy-anonymous.`
            );
        }
        const result = await models.Session.updateMany(legacySessionFilter, {
            $set: { ownerPrincipalId: `local:${user._id}` },
        });
        console.debug(`Assigned ${result.modifiedCount} legacy session(s) to ${email}`);
        models.disconnect(() => process.exit(0));
    } catch (err) {
        console.error((err as Error).message);
        models.disconnect(() => process.exit(1));
    }
});
