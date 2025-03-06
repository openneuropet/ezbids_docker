import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import ViteYaml from '@modyfi/vite-plugin-yaml';

export default defineConfig({
    base: '/ezbids/',
    plugins: [
        vue(),
        Components({
            resolvers: [ElementPlusResolver()],
        }),
        ViteYaml(),
    ],
    build: {
        sourcemap: true,
    },
    // questionable if this is required
    //define: {
    //    'process.env.VITE_APIHOST': JSON.stringify(process.env.VITE_APIHOST || 'http://localhost:8082'),
    //    'process.env.VITE_BRAINLIFE_AUTHENTICATION': JSON.stringify(
    //        process.env.VITE_BRAINLIFE_AUTHENTICATION === 'true'
    //    ),
    //},
});
