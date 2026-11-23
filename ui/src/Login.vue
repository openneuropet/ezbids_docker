<template>
    <AuthLayout title="Log in to ezBIDS">
        <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="Email">
                <el-input
                    v-model.trim="email"
                    data-testid="login-email"
                    type="email"
                    autocomplete="username"
                    @keyup.enter="submit"
                />
            </el-form-item>
            <el-form-item label="Password">
                <el-input
                    v-model="password"
                    data-testid="login-password"
                    type="password"
                    autocomplete="current-password"
                    show-password
                    @keyup.enter="submit"
                />
            </el-form-item>
            <el-alert v-if="error" data-testid="auth-error" :title="error" type="error" :closable="false" show-icon />
            <el-button data-testid="login-submit" class="submit" type="primary" :loading="submitting" @click="submit"
                >Log in</el-button
            >
            <p v-if="authState.config.registrationEnabled" class="alternate">
                Need an account? <router-link to="/register">Register</router-link>
            </p>
            <p class="alternate"><router-link to="/convert">Continue as guest</router-link></p>
        </el-form>
    </AuthLayout>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import AuthLayout from './components/AuthLayout.vue';
import { authState, login } from './auth';

export default defineComponent({
    name: 'LocalLogin',
    components: { AuthLayout },
    data: () => ({ authState, email: '', password: '', submitting: false, error: '' }),
    methods: {
        async submit() {
            if (!this.email || !this.password || this.submitting) return;
            this.submitting = true;
            this.error = '';
            try {
                await login(this.email, this.password);
                const redirect =
                    typeof this.$route.query.redirect === 'string' ? this.$route.query.redirect : '/sessions';
                await this.$router.replace(
                    redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/sessions'
                );
            } catch (error: any) {
                this.error =
                    error?.response?.data?.message || error?.response?.data?.error || 'Email or password is incorrect.';
            } finally {
                this.submitting = false;
            }
        },
    },
});
</script>

<style scoped>
.submit {
    width: 100%;
    margin-top: 16px;
}
.alternate {
    text-align: center;
    margin: 20px 0 0;
}
</style>
