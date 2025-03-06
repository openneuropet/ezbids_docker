// // Read configuration from JSON file
// import * as fs from 'fs';
// import * as path from 'path';

// let config: any = {
//     mongodb: 'mongodb://127.0.0.1:27017/ezbids',
//     presort: false
// };

// try {
//     const configPath = path.join(process.cwd(), '.env');
//     if (fs.existsSync(configPath)) {
//         const jsonConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
//         config.mongodb = jsonConfig.mongodb.connection_string;
//         config.presort = jsonConfig.handler.presort;
//     }
// } catch (error) {
//     console.warn('Failed to load config from JSON:', error);
//     console.warn('Using default configuration');
// }

// export const mongodb = config.mongodb;
// export const presort = config.presort;

// //directory to copy uploaded files (it needs to be on the same filesystem as multer incoming dir)
// export const workdir = '/tmp/ezbids-workdir';
