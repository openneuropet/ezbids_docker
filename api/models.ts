import {
    set,
    connect as mongooseConnect,
    disconnect as mongooseDisconnect,
    CallbackWithoutResult,
    Schema,
    model,
} from 'mongoose';
import { mongodb, mongoose_debug } from './config';

if (mongoose_debug) set('debug', true);

export function connect(cb: CallbackWithoutResult) {
    console.debug('connecting to mongo via: ' + mongodb);
    mongooseConnect(
        mongodb,
        {
            /* this really screwed up warehouse db..
        readPreference: 'nearest',
        writeConcern: {
            w: 'majority', //isn't this the default?
        },
        readConcernLevel: 'majority',//prevents read to grab stale data from secondary
        */
            //auto_reconnect: true, //isn't this the default?
        },
        async (err) => {
            if (err) return cb(err);
            try {
                await User.init();
                await LoginSession.init();
                await GuestSession.init();
                await LegacyGuestKey.init();
            } catch (indexError) {
                return cb(indexError);
            }
            console.debug('connected to mongo via: ' + mongodb);
            return cb(null);
        }
    );
}

export function disconnect(cb) {
    mongooseDisconnect(cb);
}

///////////////////////////////////////////////////////////////////////////////////////////////////
//
// upload sessions
//

export interface ISession {
    create_date: Date;
    update_date: Date;

    ownerId: number;
    ownerPrincipalId?: string;
    allowedUsers: number[];

    request_headers: any;
    upload_finish_date: Date;

    pre_begin_date: Date;
    pre_finish_date: Date;

    deface_begin_date: Date;
    deface_finish_date: Date;

    finalize_begin_date: Date;
    finalize_finish_date: Date;

    status: string;

    dicomCount: number;
    dicomDone: number;

    status_msg: string;
}

const sessionSchema = new Schema<ISession>({
    create_date: { type: Date, default: Date.now },
    update_date: { type: Date, default: Date.now },

    ownerId: Schema.Types.Number,
    ownerPrincipalId: { type: String, index: true },
    allowedUsers: [Schema.Types.Number],

    request_headers: Schema.Types.Mixed,

    upload_finish_date: Date, //when all files are uploaded

    pre_begin_date: Date, //when preprocessing is started
    pre_finish_date: Date, //when preprocessing is finished

    deface_begin_date: Date,
    deface_finish_date: Date,

    finalize_begin_date: Date,
    finalize_finish_date: Date,

    status: String, //just message to show to the user
    //created
    //uploaded (waiting to be preprocessed)
    //preprocessing
    //analyzed
    //finalized
    //bidsing

    //finished
    //failed

    //dcm2niix status
    dicomCount: Number,
    dicomDone: Number,

    status_msg: String,

    /*
    files: [{
        idx: Number,
        name: String,
        size: Number, 
        path: String,      
        _upload: Object, //set when the file is uploaded.. just to store some extra information from multer
    }],
    */

    //workdir: String, //directory containing uploaded file structure

    //removed: { type: Boolean, default: false },
});
sessionSchema.pre('save', function (next) {
    this.update_date = new Date();
    next();
});
export const Session = model('Session', sessionSchema);

const ezbidsSchema = new Schema({
    _session_id: Schema.Types.ObjectId,

    original: Schema.Types.Mixed,
    updated: Schema.Types.Mixed,

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date },
});
export const ezBIDS = model('ezBIDS', ezbidsSchema);

const userSchema = new Schema({
    email: { type: String, required: true, unique: true },
    displayName: { type: String, required: true },
    passwordHash: { type: String, required: true, select: false },
    role: { type: String, enum: ['user', 'admin'], default: 'user' },
    disabled: { type: Boolean, default: false },
    create_date: { type: Date, default: Date.now },
});
export const User = model('User', userSchema);
const loginSessionSchema = new Schema({
    tokenHash: { type: String, required: true, unique: true },
    userId: { type: Schema.Types.ObjectId, ref: 'User', required: true },
    expiresAt: { type: Date, required: true, expires: 0 },
});
export const LoginSession = model('LoginSession', loginSessionSchema);

const guestSessionSchema = new Schema({
    tokenHash: { type: String, required: true, unique: true },
    guestId: { type: String, required: true },
    legacy: { type: Boolean, default: false },
    expiresAt: { type: Date, required: true, expires: 0 },
});
export const GuestSession = model('GuestSession', guestSessionSchema);
export const LegacyGuestKey = model(
    'LegacyGuestKey',
    new Schema({
        keyId: { type: String, required: true, unique: true },
        publicKey: { type: String, required: true },
    })
);
