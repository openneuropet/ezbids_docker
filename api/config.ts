'use strict';

// Hardcoded MongoDB connection string using container IP
// We're using a fixed IP (10.22.0.19) instead of hostname 'mongodb' because:
// 1. Environment variables aren't being properly passed to the Apptainer container
// 2. DNS resolution for container hostnames isn't working in Apptainer networking
// TODO: Remove this hardcoding once we resolve environment variable passing in Apptainer
// Original configuration:
export const mongodb = process.env.MONGO_CONNECTION_STRING || 'mongodb://mongodb:27017/ezbids';
// export const mongodb = process.env.MONGO_CONNECTION_STRING || 'mongodb://127.0.0.1:27017/ezbids';

export const mongoose_debug = true;
//multer incoming upload directory
export const multer = {
    dest: '/tmp/upload',
};
//directory to copy uploaded files (it needs to be on the same filesystem as multer incoming dir)
export const workdir = '/tmp/ezbids-workdir';
export const express = {
    host: '0.0.0.0',
    port: '8082',
};

export const authentication = process.env.BRAINLIFE_AUTHENTICATION === 'true';
