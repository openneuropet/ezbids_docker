<template>
    <div class="auth-page">
        <el-card class="auth-card">
            <template #header>
                <div class="heading">
                    <router-link to="/" class="brand"><span>ez</span>BIDS</router-link>
                    <h1>{{ title }}</h1>
                </div>
            </template>
            <slot />
        </el-card>
    </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>();
</script>

<style scoped>
.auth-page {
    min-height: 100%;
    display: grid;
    place-items: center;
    padding: 30px 16px;
    box-sizing: border-box;
    background: linear-gradient(135deg, #eefaf6, #edf4fc);
}
.auth-card {
    width: min(420px, 100%);
}
.heading {
    text-align: center;
}
.heading h1 {
    margin: 14px 0 2px;
    font-size: 1.4rem;
}
.brand {
    color: #245d91;
    font-size: 1.7rem;
    font-weight: bold;
    text-decoration: none;
}
.brand span {
    opacity: 0.65;
    letter-spacing: -2px;
}
</style>
