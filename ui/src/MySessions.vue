<template>
    <main class="sessions" data-testid="sessions-page">
        <h1>My sessions</h1>
        <p data-testid="sessions-identity">Signed in as {{ authState.user?.email }}</p>
        <el-button data-testid="sessions-new" type="primary" @click="newSession">New session</el-button>
        <el-button data-testid="sessions-logout" @click="signOut">Log out</el-button>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <p v-if="loading" data-testid="sessions-loading">Loading sessions…</p>
        <p v-else-if="!sessions.length && !error" data-testid="sessions-empty">You have no previous sessions yet.</p>
        <el-table v-else data-testid="sessions-table" :data="sessions">
            <el-table-column prop="_id" label="Session" />
            <el-table-column prop="create_date" label="Created" />
            <el-table-column prop="status" label="Status" />
            <el-table-column label="">
                <template #default="scope">
                    <el-button
                        data-testid="sessions-open"
                        :data-session-id="scope.row._id"
                        @click="openSession(scope.row._id)"
                        >Open</el-button
                    >
                </template>
            </el-table-column>
        </el-table>
        <el-button v-if="hasMore" :loading="loading" @click="loadMore">Load older sessions</el-button>
    </main>
</template>
<script lang="ts">
import { defineComponent } from 'vue';
import axios from './axios.instance';
import { authState, authUrl, logout } from './auth';
export default defineComponent({
    data: () => ({ authState, sessions: [] as any[], loading: true, hasMore: false, error: '' }),
    async mounted() {
        await this.loadMore();
    },
    methods: {
        async loadMore() {
            this.loading = true;
            this.error = '';
            try {
                const before = this.sessions.length ? this.sessions[this.sessions.length - 1]._id : undefined;
                const rows = (await axios.get(authUrl('/sessions'), { params: { before } })).data;
                this.sessions.push(...rows);
                this.hasMore = rows.length === 50;
            } catch {
                this.error = 'Unable to load your sessions. Please try again.';
            } finally {
                this.loading = false;
            }
        },
        async newSession() {
            this.$store.commit('reset');
            await this.$router.push({ path: '/convert', hash: '' });
        },
        async openSession(id: string) {
            try {
                await this.$router.push({ path: '/convert', hash: `#${id}` });
            } catch {
                this.error = 'Unable to open this session.';
            }
        },
        async signOut() {
            await logout();
            window.location.assign('/ezbids/login');
        },
    },
});
</script>
<style scoped>
.sessions {
    max-width: 1100px;
    margin: 40px auto;
    padding: 0 20px;
}
.el-table {
    margin-top: 24px;
}
</style>
