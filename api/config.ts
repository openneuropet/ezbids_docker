'use strict';
export const mongodb = process.env.MONGO_CONNECTION_STRING || 'mongodb://mongodb:27017/ezbids';
export const mongoose_debug = process.env.MONGOOSE_DEBUG === 'true';
//multer incoming upload directory
export const multer = {
    dest: '/tmp/upload',
};
//directory to copy uploaded files (it needs to be on the same filesystem as multer incoming dir)
export const workdir = '/tmp';
export const express = {
    host: '0.0.0.0',
    port: '8082',
};

export const authentication = process.env.BRAINLIFE_AUTHENTICATION === 'true';

export type AuthMode = 'disabled' | 'brainlife' | 'local';
const requestedAuthMode = process.env.EZBIDS_AUTH_MODE || (authentication ? 'brainlife' : 'local');
if (!['disabled', 'brainlife', 'local'].includes(requestedAuthMode)) throw new Error('Invalid EZBIDS_AUTH_MODE');
export const authMode = requestedAuthMode as AuthMode;
export const registrationEnabled = authMode === 'local' && process.env.EZBIDS_REGISTRATION_ENABLED !== 'false';
export const secureCookies = process.env.EZBIDS_SECURE_COOKIES === 'true';
export const allowedOrigins = (process.env.EZBIDS_ALLOWED_ORIGINS || 'http://localhost:3000,http://127.0.0.1:3000')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

// Empty by default for directly exposed API ports. Only deployment operators
// may configure trusted peer addresses or private-network DNS service names.
export const trustedProxies = (process.env.EZBIDS_TRUSTED_PROXIES || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
export const trustedProxyNames = (process.env.EZBIDS_TRUSTED_PROXY_NAMES || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
