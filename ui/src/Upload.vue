<template>
    <div style="padding: 20px">
        <div v-if="!session">
            <p>
                Welcome to <b><span style="letter-spacing: -2px; opacity: 0.5">ez</span>BIDS</b> - an online imaging
                data to BIDS conversion / organizing tool.
            </p>

            <div v-if="!starting">
                <div class="select-area">
                    <div class="select-area-backdrop">
                        <b><span style="letter-spacing: -4vh">ez</span>BIDS</b>
                    </div>
                    <div>
                        <b>Select a folder containing DICOM (or dcm2niix) data</b>
                        <br />
                        <br />
                        <el-button type="primary" size="large" @click="selectDirectory">
                            Select Directory
                        </el-button>
                        <br />
                        <br />
                        <small style="opacity: 0.7">Requires Chrome or Edge browser</small>
                    </div>
                </div>

                <div class="Info">
                    <h2>Information</h2>
                    <ul style="line-height: 200%">
                        <li>
                            If you are new to ezBIDS, please view our
                            <a href="https://brainlife.io/docs/tutorial/ezBIDS/" target="_blank"
                                ><b>ezBIDS tutorial</b></a
                            >
                            and
                            <a href="https://brainlife.io/docs/using_ezBIDS/" target="_blank"
                                ><b>user documentation</b></a
                            >.
                        </li>
                        <li>
                            If uploading anonymized data, please organize subject data into <i>sub-</i>formatted folder
                            names (e.g. <b>sub-01</b>). If you have multi-session data, place in <i>ses-</i>formatted
                            folders (e.g. <b>ses-A</b>) within the subject folders.
                        </li>
                        <li>See below for a brief ezBIDS tutorial video.</li>
                    </ul>
                    <iframe
                        width="640"
                        height="360"
                        src="https://www.youtube.com/embed/L8rWA8qgnpo"
                        title="YouTube video player"
                        frameborder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen
                    ></iframe>
                </div>
                <br />
                <br />
                <br />
            </div>

            <div v-if="starting">
                <h3>Initializing ...</h3>
            </div>
        </div>

        <div v-if="session">
            <div v-if="session.status == 'created'">
                <h3>
                    Uploading
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <small>Please do not close or refresh this page until all files are uploaded.</small>
                <div v-if="failedFiles.length > 0">
                    <el-alert type="error"
                        >Permanently failed to upload some files, please email anthony.galassi@nih.gov for
                        assistance or create an issue at https://github.com/openneuropet/ezbids_docker</el-alert
                    >
                    <pre v-for="(entry, idx) in failedFiles" :key="idx" type="info" style="font-size: 80%">{{ entry.path }}</pre>
                </div>

                <p>
                    <small>Uploaded {{ formatNumber(uploadedSize / (1024 * 1024)) }} MB</small>
                    <small> | {{ totalFiles }} Files </small>
                    <small> ({{ uploadedCount }} uploaded) </small>
                    <el-progress
                        status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="uploadProgress"
                    />
                </p>
                <div v-for="(batch, idx) in batches" :key="idx">
                    <div v-if="batch.status != 'done'" class="batch-stat">
                        <b style="text-transform: uppercase">{{ batch.status }}</b>
                        batch {{ (idx + 1).toString() }}. {{ batch.entries.length }} files
                        <span> ({{ formatNumber(batch.size / (1024 * 1024)) }} MB) </span>
                        <div style="height: 20px">
                            <el-progress
                                v-if="batch.evt.total"
                                :status="batchStatus(batch)"
                                :text-inside="true"
                                :stroke-width="15"
                                :percentage="parseFloat(((batch.evt.loaded / batch.evt.total) * 100).toFixed(1))"
                            />
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="['preprocessing', 'uploaded'].includes(session.status)">
                <h3 v-if="session.dicomDone === undefined">
                    Inflating
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <div v-else-if="session.dicomDone < session.dicomCount">
                    <h3>
                        Converting DICOMS to NIfTI
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                    <el-progress
                        status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="parseFloat(((session.dicomDone * 100) / session.dicomCount).toFixed(1))"
                    />
                    <br />
                </div>
                <h3 v-else>
                    Analyzing
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <pre class="status">{{ session.status_msg }}</pre>
                <small
                    >* Depending on the size of your dataset, this process might take several hours. You can shutdown
                    your computer while we process your data (please bookmark the URL for this page to come back to
                    it)</small
                >
            </div>

            <div v-if="session.status == 'failed'">
                <el-alert type="error"
                    >ezBIDS failed.. Please check the Debug logs and contact anthony.galassi@nih.gov
                    or create an issue at https://github.com/openneuropet/ezbids_docker</el-alert
                >
                <br />
                <pre class="status">{{ session.status_msg }}</pre>
            </div>

            <div v-if="session.pre_finish_date">
                <div v-if="ezbids.notLoaded">
                    <h3>
                        Loading analysis results
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                </div>

                <div v-if="!ezbids.notLoaded && ezbids.objects.length">
                    <h2>Analysis complete!</h2>
                    <AnalysisErrors />
                    <h3>
                        Object List <small>({{ ezbids.objects.length }})</small>
                    </h3>
                    <p>
                        <small
                            >We have identified the following files (objects) that can be organized into BIDS
                            structure.</small
                        >
                    </p>
                    <div v-for="(object, idx) in ezbids.objects" :key="idx" style="padding-bottom: 2px">
                        <p style="margin: 0">
                            <el-link @click="toggleObject(idx)">
                                <small>
                                    <el-tag size="mini" type="info">{{ idx }}</el-tag>
                                    {{ itemPath(object.items) }}
                                </small>
                            </el-link>
                        </p>
                        <pre v-if="opened.includes(idx)" class="status">{{ object }}</pre>
                    </div>
                </div>
                <div v-if="!ezbids.notLoaded && !ezbids.objects.length">
                    <el-alert type="error"
                        >We couldn't find any objects. Please upload data that contains at least 1 object. Contact
                        anthony.galassi@nih.gov or https://github.com/openneuropet/ezbids_docker/issues for
                        support</el-alert
                    >
                </div>
            </div>

            <br />
            <el-collapse>
                <el-collapse-item title="Debug (Download)">
                    <ul style="list-style: none; padding-left: 0">
                        <el-button
                            style="width: 168px"
                            type="warning"
                            size="mini"
                            @click="downloadFile('preprocess.log')"
                            >preprocess.log</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('preprocess.err')"
                            >preprocess.err</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('dcm2niix_error')"
                            >dcm2niix_error</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('pet2bids_error')"
                            >pet2bids_error</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('list')">data list</el-button>
                        <el-button type="warning" size="mini" @click="downloadFile('ezBIDS_core.json')"
                            >ezBIDS_core.json</el-button
                        >
                    </ul>

                    <el-button type="info" style="width: 168px" size="mini" @click="dump">Dump state</el-button>
                    <br />

                </el-collapse-item>
            </el-collapse>
            <br />
            <br />
            <br />
        </div>
    </div>
</template>

<script>
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { formatNumber } from './filters';
import axios from './axios.instance';
import { ElNotification } from 'element-plus';

export default defineComponent({
    components: {
        AnalysisErrors: () => import('./components/analysisErrors.vue'),
    },
    data() {
        return {
            starting: false,

            // File System Access API - stores { handle, path, retries }
            pendingFiles: new Set(),
            failedFiles: [],
            uploadedCount: 0,
            totalFiles: 0,
            uploadedSize: 0, // calculated lazily as batches complete

            batches: [], // { entries, evt, status, size }

            opened: [],
            doneUploading: false,

            activeLogs: [],
            list: '',
        };
    },

    computed: {
        ...mapState(['session', 'config', 'ezbids']),

        uploadProgress() {
            if (this.totalFiles === 0) return 0;
            return parseFloat(((this.uploadedCount / this.totalFiles) * 100).toFixed(1));
        },
    },

    methods: {
        async downloadFile(fileName) {
            if (!fileName) return;
            try {
                const res = await axios.get(`${this.config.apihost}/download/${this.session._id}/token`);
                const shortLivedJWT = res.data;

                window.location.href = `${this.config.apihost}/download/${this.session._id}/${fileName}?token=${shortLivedJWT}`;
            } catch (e) {
                console.error(e);
                ElNotification({
                    message: 'there was an error downloading the file',
                    type: 'error',
                });
            }
        },

        formatNumber,

        toggleObject(idx) {
            let pos = this.opened.indexOf(idx);
            if (~pos) this.opened.splice(pos, 1);
            else this.opened.push(idx);
        },

        batchStatus(batch) {
            switch (batch.status) {
                case 'done':
                    return 'success';
                case 'failed':
                    return 'exception';
            }
            return null;
        },

        async selectDirectory() {
            try {
                const dirHandle = await window.showDirectoryPicker();
                this.starting = true;
                this.pendingFiles = new Set();
                this.failedFiles = [];
                this.uploadedCount = 0;
                this.uploadedSize = 0;
                this.batches = [];
                this.totalFiles = 0;
                await this.collectHandles(dirHandle, dirHandle.name);
                // Set totalFiles after collection completes to ensure accurate count
                this.totalFiles = this.pendingFiles.size;
                console.log(`Collected ${this.totalFiles} files for upload`);
                this.startUpload();
            } catch (err) {
                if (err.name !== 'AbortError') console.error(err);
            }
        },

        async collectHandles(dirHandle, basePath) {
            for await (const entry of dirHandle.values()) {
                const path = `${basePath}/${entry.name}`;
                if (entry.kind === 'file') {
                    this.pendingFiles.add({ handle: entry, path, retries: 0 });
                } else if (entry.kind === 'directory') {
                    await this.collectHandles(entry, path);
                }
            }
        },

        async startUpload() {
            this.starting = false;
            this.doneUploading = false;

            // Create new session
            const res = await axios.post(`${this.config.apihost}/session`, {
                headers: { 'Content-Type': 'application/json' },
            });
            this.$store.commit('setSession', await res.data);
            this.processFiles();
        },

        async processFiles() {
            // Build a batch from pending files (lazy file access)
            const data = new FormData();
            const batchEntries = [];
            let batchSize = 0;

            for (const entry of this.pendingFiles) {
                if (entry.uploading) continue;
                if (entry.retries > 5) {
                    this.pendingFiles.delete(entry);
                    this.failedFiles.push(entry);
                    continue;
                }

                // Mark as uploading BEFORE any async operation to prevent race condition
                entry.uploading = true;

                // Get the actual File object only now (lazy access)
                const file = await entry.handle.getFile();
                entry.file = file; // Store for retry if needed
                batchSize += file.size;

                // Limit batch size - if exceeded, release entry for next batch
                if (batchEntries.length > 0 && (batchEntries.length >= 500 || batchSize > 1024 * 1024 * 300)) {
                    entry.uploading = false;
                    break;
                }

                batchEntries.push(entry);
                data.append('files', file);
                data.append('paths', entry.path);
                data.append('mtimes', file.lastModified);
            }

            if (batchEntries.length === 0) {
                return;
            }

            const batch = { entries: batchEntries, evt: {}, status: 'uploading', size: batchSize };
            this.batches.push(batch);

            const doSend = () => {
                axios
                    .post(this.config.apihost + '/upload-multi/' + this.session._id, data, {
                        onUploadProgress: (evt) => {
                            batch.evt = evt;
                        },
                    })
                    .then((res) => {
                        if (res.data === 'ok') {
                            batch.status = 'done';
                            // Remove successfully uploaded entries from Set
                            for (const entry of batchEntries) {
                                this.pendingFiles.delete(entry);
                                this.uploadedCount++;
                                this.uploadedSize += entry.file.size;
                            }

                            if (this.pendingFiles.size === 0) {
                                this.done();
                            } else {
                                this.processFiles();
                            }
                        } else {
                            batch.status = 'failed';
                            console.error(res);
                        }
                    })
                    .catch((err) => {
                        batch.status = 'failed';
                        // Mark for retry
                        for (const entry of batchEntries) {
                            entry.retries++;
                            entry.uploading = false;
                        }
                        setTimeout(() => this.processFiles(), 1000 * 13);
                    })
                    .then(() => {
                        for (const entry of batchEntries) {
                            entry.uploading = false;
                        }
                    });

                // Start more batches if under limit
                const uploadingBatches = this.batches.filter((b) => b.status === 'uploading');
                if (uploadingBatches.length < 4) {
                    setTimeout(() => this.processFiles(), 1000 * 3);
                }
            };

            doSend();
        },

        async done() {
            if (this.doneUploading) return;
            this.doneUploading = true;

            // Mark the session as uploaded
            await axios.patch(`${this.config.apihost}/session/uploaded/${this.session._id}`, {
                headers: { 'Content-Type': 'application/json' },
            });

            // Construct dataset description from first uploaded path
            if (this.batches.length > 0 && this.batches[0].entries.length > 0) {
                const firstPath = this.batches[0].entries[0].path;
                const tokens = firstPath.split('/');
                const desc = tokens[0];
                this.$store.state.ezbids.datasetDescription.Name = desc;
            }
        },

        isValid(cb) {
            //TODO..
            cb();
        },

        dump() {
            var element = document.createElement('a');
            element.setAttribute(
                'href',
                'data:text/plain;charset=utf-8,' + encodeURIComponent(JSON.stringify(this.ezbids, null, 4))
            );
            element.setAttribute('download', 'root.json');
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        },

        itemPath(items) {
            let str = '';
            items.forEach((item) => {
                if (str == '') str = item.path;
                else {
                    //for subsequent path, skip the parts that's same
                    const strtokens = str.split('.');
                    const pathtokens = item.path.split('.');
                    const unique = [];
                    str += ' / ';
                    for (let i = 0; i < pathtokens.length; ++i) {
                        if (pathtokens[i] == strtokens[i]) continue;
                        else str += '.' + pathtokens[i];
                    }
                }
            });
            return str;
        },
    },
});
</script>

<style lang="scss" scoped>
.select-area {
    z-index: 0;
    background-color: #0002;
    color: #999;
    padding: 25px;
    padding-top: 100px;
    border-radius: 5px;
    height: 300px;
    box-sizing: border-box;
    font-size: 125%;
    position: relative;
    overflow: hidden;
    text-align: center;
}
.select-area-backdrop {
    position: absolute;
    font-size: 25vh;
    opacity: 0.1;
    top: 0;
    left: 0;
    right: 0;
    z-index: -1;
    padding: 30px 0;
    filter: blur(0.5vh);
}
.batch-stat {
    font-family: monospace;
    font-size: 90%;
}

pre.status {
    background-color: #666;
    color: white;
    height: 300px;
    overflow: auto;
    padding: 10px;
    margin-top: 0;
    margin-bottom: 5px;
    border-radius: 5px;
}
</style>
