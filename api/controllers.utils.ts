import { NextFunction, Response } from 'express';
import { Request } from 'express-jwt';
import { ISession, Session } from './models';
import { Types, Document } from 'mongoose';
import * as config from './config';
import { userCanAccessSession } from './access-policy';
import { principalId } from './auth';

export enum HTTP_STATUS {
    OK = 200,
    BAD_REQUEST = 400,
    UNAUTHORIZED = 401,
    NOT_FOUND = 404,
    INTERNAL_SERVER_ERROR = 500,
}

export type EzBIDSAuthRequestObject = Request & {
    ezBIDS: {
        session: Document<unknown, any, ISession> &
            Omit<
                ISession & {
                    _id: Types.ObjectId;
                },
                never
            >;
    };
};

export const validateUserCanAccessSession = (onlyOwnerCanAccess: boolean) => {
    return (req: EzBIDSAuthRequestObject, res: Response, next: NextFunction) => {
        const sessionId = req.params.session_id;
        const userId = req.auth.sub as unknown as number;

        if (!sessionId || !Types.ObjectId.isValid(sessionId)) {
            return res.status(HTTP_STATUS.BAD_REQUEST).json({ err: 'No sessionId found' });
        }

        if (config.authMode !== 'disabled' && !userId) {
            return res.status(HTTP_STATUS.BAD_REQUEST).json({ err: 'No userId found' });
        }

        return Session.findById(sessionId)
            .then((session) => {
                if (!session)
                    return res
                        .status(HTTP_STATUS.NOT_FOUND)
                        .json({ err: 'Could not find session with ID: ' + sessionId });

                if (
                    !userCanAccessSession(config.authMode, principalId(req), req.auth.sub, session, onlyOwnerCanAccess)
                ) {
                    return res.status(404).json({ message: 'Session not found' });
                }

                req.ezBIDS = {
                    session,
                };
                return next();
            })
            .catch((err) => {
                console.error(err);
                return res.status(HTTP_STATUS.INTERNAL_SERVER_ERROR).send({ err: 'internal server error' });
            });
    };
};
