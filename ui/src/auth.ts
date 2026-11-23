import axios from 'axios';
import { reactive } from 'vue';

export type AuthMode = 'disabled' | 'brainlife' | 'local';

export interface AuthUser {
    _id?: string;
    id?: string;
    email: string;
    displayName?: string;
    fullname?: string;
    role: 'admin' | 'user';
    disabled?: boolean;
}

export interface AuthConfig {
    mode: AuthMode;
    registrationEnabled: boolean;
}

const apiBase = import.meta.env.VITE_APIHOST || '/api/ezbids';
const configuredMode = import.meta.env.VITE_EZBIDS_AUTH_MODE;
const legacyBrainlifeMode = import.meta.env.VITE_BRAINLIFE_AUTHENTICATION === 'true';
let fallbackMode: AuthMode = legacyBrainlifeMode ? 'brainlife' : 'local';
if (configuredMode && ['disabled', 'brainlife', 'local'].includes(configuredMode)) {
    fallbackMode = configuredMode as AuthMode;
}

export const authState = reactive({
    config: {
        mode: fallbackMode,
        registrationEnabled: false,
    },
    user: null as AuthUser | null,
    configLoaded: false,
    userLoaded: false,
});

let configRequest: Promise<AuthConfig> | null = null;
let userRequest: Promise<AuthUser | null> | null = null;

function normalizeConfig(data: any): AuthConfig {
    const mode = data?.mode || data?.authMode || data?.authenticationMode;
    return {
        mode: ['disabled', 'brainlife', 'local'].includes(mode) ? mode : authState.config.mode,
        registrationEnabled: Boolean(data?.registrationEnabled ?? data?.registration_enabled),
    };
}

function normalizeUser(data: any): AuthUser | null {
    const user = data?.user ?? data;
    if (!user || (!user.email && !user._id && !user.id)) return null;
    return {
        ...user,
        email: user.email || '',
        displayName: user.displayName ?? user.name ?? user.fullname,
        role: user.role === 'admin' || user.isAdmin ? 'admin' : 'user',
    };
}

export function authUrl(path: string) {
    return `${apiBase}${path}`;
}

export async function loadAuthConfig(force = false): Promise<AuthConfig> {
    if (authState.configLoaded && !force) return authState.config;
    if (configRequest && !force) return configRequest;

    configRequest = axios
        .get(authUrl('/auth/config'))
        .then((response) => {
            authState.config = normalizeConfig(response.data);
            return authState.config;
        })
        .catch((error) => {
            // Use the configured Brainlife or local mode if runtime configuration is unavailable.
            if (error?.response?.status !== 404) console.warn('Unable to load authentication configuration', error);
            return authState.config;
        })
        .finally(() => {
            authState.configLoaded = true;
            configRequest = null;
        });
    return configRequest;
}

export async function loadCurrentUser(force = false): Promise<AuthUser | null> {
    await loadAuthConfig();
    if (authState.config.mode !== 'local') {
        authState.user = null;
        authState.userLoaded = true;
        return null;
    }
    if (authState.userLoaded && !force) return authState.user;
    if (userRequest && !force) return userRequest;

    userRequest = axios
        .get(authUrl('/auth/me'), { withCredentials: true })
        .then((response) => {
            authState.user = normalizeUser(response.data);
            return authState.user;
        })
        .catch((error) => {
            if (error?.response?.status !== 401) throw error;
            authState.user = null;
            return null;
        })
        .finally(() => {
            authState.userLoaded = true;
            userRequest = null;
        });
    return userRequest;
}

export function isAuthenticated() {
    switch (authState.config.mode) {
        case 'disabled':
            return true;
        case 'brainlife':
            return Boolean(localStorage.getItem('jwt'));
        case 'local':
            return Boolean(authState.user);
    }
}

export async function login(email: string, password: string) {
    const response = await axios.post(authUrl('/auth/login'), { email, password }, { withCredentials: true });
    authState.user = normalizeUser(response.data);
    authState.userLoaded = Boolean(authState.user);
    if (!authState.user) await loadCurrentUser(true);
    return authState.user;
}

export async function register(displayName: string, email: string, password: string) {
    const response = await axios.post(
        authUrl('/auth/register'),
        { displayName, email, password },
        { withCredentials: true }
    );
    authState.user = normalizeUser(response.data);
    authState.userLoaded = Boolean(authState.user);
    if (!authState.user) await loadCurrentUser(true);
    return authState.user;
}

export async function logout() {
    if (authState.config.mode === 'local') {
        await axios.post(authUrl('/auth/logout'), undefined, { withCredentials: true });
        authState.user = null;
        authState.userLoaded = true;
    }
}
