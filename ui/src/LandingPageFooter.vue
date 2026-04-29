<template>
    <el-footer class="footer">
        <el-row style="height: 100%">
            <el-col :span="1"></el-col>
            <el-col :span="23" class="disclaimer">
                <div style="display: flex; flex-direction: column; justify-content: center; height: 100%;">
                    <div>© Pestillilab. All rights reserved.</div>
                    <div style="font-size: 0.85em; margin-top: 0.25em; opacity: 0.9;">
                        This is a fork of ezBIDS with additional PET support. 
                        Source code available at 
                        <a href="https://github.com/openneuropet/ezbids_docker" target="_blank" style="color: white; text-decoration: underline;">github.com/openneuropet/ezbids_docker</a>
                    </div>
                </div>
            </el-col>
        </el-row>
    </el-footer>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({});
</script>

<style scoped>
.footer {
    padding: 0;
    background-color: #3782e5;
    color: white;
    height: 10vh;
}

.disclaimer {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
}
</style>
