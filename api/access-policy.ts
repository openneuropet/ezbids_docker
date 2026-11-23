import { AuthMode } from './config';

export type SessionAccessRecord = {
    ownerPrincipalId?: string;
    ownerId?: number;
    allowedUsers?: number[];
};

export const userCanAccessSession = (
    authMode: AuthMode,
    principalId: string,
    subject: string | number,
    session: SessionAccessRecord,
    onlyOwnerCanAccess: boolean
): boolean => {
    if (authMode === 'disabled') return true;
    if (authMode === 'local') return session.ownerPrincipalId === principalId;

    const isOwner =
        session.ownerPrincipalId === principalId ||
        (session.ownerId !== undefined && String(session.ownerId) === String(subject));
    if (isOwner) return true;
    if (onlyOwnerCanAccess) return false;
    return (session.allowedUsers || []).some((allowedUser) => String(allowedUser) === String(subject));
};
