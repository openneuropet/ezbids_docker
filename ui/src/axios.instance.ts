import axios from 'axios';
import { ElNotification } from 'element-plus';
import router from './routes';
import { hasAuth } from './lib';
import { authState } from './auth';

const axiosInstance = axios.create({
    headers: { 'Content-Type': 'application/json; charset=UTF-8' },
});

axiosInstance.interceptors.request.use((config) => {
    config.withCredentials = authState.config.mode === 'local';
    if (authState.config.mode !== 'brainlife' || !hasAuth()) return config;
    const token = localStorage.getItem('jwt');
    if (token) {
        config.headers = {
            ...config.headers,
            Authorization: `Bearer ${token}`,
        };
    } else {
        ElNotification({
            title: 'Unauthorized user',
            message: '',
            type: 'error',
        });
    }
    return config;
});

axiosInstance.interceptors.response.use(
    (response) => response,
    (err) => {
        if (err.response) {
            if (err.response.status === 401) {
                authState.user = null;
                authState.userLoaded = true;
                router.push(authState.config.mode === 'local' ? '/login' : '/');
                ElNotification({
                    title: 'Unauthorized access',
                    message: '',
                    type: 'error',
                });
            }
        }
        throw err;
    }
);

export default axiosInstance;
