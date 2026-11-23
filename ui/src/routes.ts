import { createRouter, createWebHistory } from 'vue-router';
import LandingPage from './LandingPage.vue';
import BaseConvertPage from './BaseConvertPage.vue';
import NotFound from './NotFound.vue';
import Login from './Login.vue';
import Register from './Register.vue';
import MySessions from './MySessions.vue';
import { authState, loadAuthConfig, loadCurrentUser } from './auth';
import { hasJWT, hasAuth } from './lib';
import { ElNotification } from 'element-plus';

// enable routing
const router = createRouter({
    history: createWebHistory('/ezbids'),
    routes: [
        { path: '/', name: 'base', component: LandingPage },
        { path: '/login', name: 'login', component: Login },
        { path: '/register', name: 'register', component: Register },
        { path: '/sessions', name: 'sessions', component: MySessions },
        { path: '/convert', name: 'convert', component: BaseConvertPage },
        { path: '/:pathMatch(.*)*', component: NotFound },
    ],
});

router.beforeEach(async (to, from) => {
    await loadAuthConfig();
    if (authState.config.mode === 'local') {
        await loadCurrentUser();
        if (to.name === 'register' && !authState.config.registrationEnabled) return { name: 'login' };
        if (to.name === 'sessions' && !authState.user) {
            return { name: 'login', query: { redirect: to.fullPath } };
        }
        if (['login', 'register'].includes(String(to.name)) && authState.user) return { name: 'sessions' };
        return true;
    }
    if (['login', 'register', 'sessions'].includes(String(to.name))) return { name: 'base' };
    if (hasAuth() && !hasJWT() && to.name !== 'base') {
        ElNotification({
            title: 'Please login to continue',
            message: '',
            type: 'error',
        });
        return { name: 'base' }; // route back to landing page
    }
    return true;
});

export default router;
