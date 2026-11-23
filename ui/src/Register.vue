<template>
    <AuthLayout title="Create an ezBIDS account">
        <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="Name">
                <el-input v-model.trim="displayName" autocomplete="name" />
            </el-form-item>
            <el-form-item label="Email">
                <el-input v-model.trim="email" type="email" autocomplete="username" />
            </el-form-item>
            <el-form-item label="Password">
                <el-input v-model="password" type="password" autocomplete="new-password" show-password />
            </el-form-item>
            <el-form-item label="Confirm password">
                <el-input
                    v-model="confirmPassword"
                    type="password"
                    autocomplete="new-password"
                    show-password
                    @keyup.enter="submit"
                />
            </el-form-item>
            <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
            <el-button class="submit" type="primary" :loading="submitting" @click="submit">Create account</el-button>
            <p class="alternate">Already registered? <router-link to="/login">Log in</router-link></p>
            <p class="alternate"><router-link to="/convert">Continue as guest</router-link></p>
        </el-form>
    </AuthLayout>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import AuthLayout from './components/AuthLayout.vue';
import { register } from './auth';

export default defineComponent({
    name: 'LocalRegistration',
    components: { AuthLayout },
    data: () => ({ displayName: '', email: '', password: '', confirmPassword: '', submitting: false, error: '' }),
    methods: {
        async submit() {
            if (this.submitting) return;
            this.error = '';
            if (!this.displayName || !this.email || !this.password) {
                this.error = 'All fields are required.';
                return;
            }
            if (this.password !== this.confirmPassword) {
                this.error = 'Passwords do not match.';
                return;
            }
            if (this.password.length < 12) {
                this.error = 'Password must contain at least 12 characters.';
                return;
            }
            this.submitting = true;
            try {
                await register(this.displayName, this.email, this.password);
                await this.$router.replace('/sessions');
            } catch (error: any) {
                this.error =
                    error?.response?.data?.message || error?.response?.data?.error || 'Unable to create the account.';
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
