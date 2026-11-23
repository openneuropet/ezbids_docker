<template>
    <el-dialog v-model="open" :title="path" width="70%" destroy-on-close center @close="close">
        <canvas ref="canvas" class="canvas" height="500" />
    </el-dialog>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';

// @ts-ignore
import { Niivue, NVImage } from '@niivue/niivue';
import axios from '../axios.instance';

const nv = new Niivue({
    dragAndDropEnabled: false,
});

export default defineComponent({
    props: ['path'],
    emits: ['close'],
    data() {
        return {
            open: false,
        };
    },

    computed: {
        ...mapState(['session', 'config']),
    },

    watch: {
        path() {
            if (this.path) this.load();
        },
    },

    mounted() {
        if (this.path) this.load();
    },

    methods: {
        async load() {
            const requestedPath = this.path;
            const token = await axios.get(`${this.config.apihost}/download/${this.session._id}/token`);
            const url = `${this.config.apihost}/download/${this.session._id}/${requestedPath}?token=${encodeURIComponent(token.data)}`;
            // Niivue 0.21.1 uses bare fetch(url), which omits cookies across
            // ports. Download through our credential-aware Axios client and
            // give Niivue the bytes instead of weakening download authorization.
            const response = await axios.get(url, { responseType: 'arraybuffer' });
            if (this.path !== requestedPath) return;
            this.open = true;
            await this.$nextTick();
            await nv.attachToCanvas(this.$refs.canvas);
            const volume = new NVImage(response.data, requestedPath.split('/').pop(), 'gray', 1);
            for (const previous of [...nv.volumes]) nv.removeVolume(previous);
            nv.addVolume(volume);
        },

        close() {
            this.open = false;
            this.$emit('close');
        },
    },
});
</script>
<style scoped>
.datatype {
    font-size: 90%;
}
.bull {
    width: 8px;
    height: 8px;
    display: inline-block;
    border-radius: 50%;
    position: relative;
    top: 3px;
}
.canvas {
    width: 100%;
}
</style>
