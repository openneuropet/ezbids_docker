#!/usr/bin/node

import express = require('express');
import bodyParser = require('body-parser');
import compression = require('compression');
import cors = require('cors');
import nocache = require('nocache');

import models = require("./models");
import config = require("./config");

//import sendSeekable = require('send-seekable');

// setup swagger
import swaggerUi = require('swagger-ui-express');
import swaggerJsdoc = require('swagger-jsdoc');

const options = {
    definition: {
        openapi: '3.0.0',
        info: {
            title: 'EZBIDS API',
            version: '1.0.0',
        },
    },
    apis: ['./controllers.js'], // files containing annotations as above
};
const swaggerSpec = swaggerJsdoc(options);
//init express
const app: express.Application = express();
app.use(cors());
app.use(compression());
app.use(nocache());
//app.use(sendSeekable);

app.disable('x-powered-by'); //for better security?

app.use(bodyParser.urlencoded({
    limit: '50gb',
    extended: true
}));

app.use(bodyParser.json({
    limit: '50mb',
    type: "application/json",
}));

app.use('/', require('./controllers'));
app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));
//error handling
//app.use(expressWinston.errorLogger(config.logger.winston)); 
app.use(function (err, req, res, next) {
    if (typeof err == "string") err = { message: err };

    if (!err.name || err.name != "UnauthorizedError") {
        console.error(err);
    }

    if (err.stack) err.stack = "hidden"; //don't sent call stack to UI - for security reason
    res.status(err.status || 500);
    res.json(err);
});

process.on('uncaughtException', err => {
    //TODO report this to somewhere!
    console.error((new Date).toUTCString() + ' uncaughtException:', err.message)
    console.error(err.stack)
});

models.connect(err => {
    if (err) throw err;
    var port = parseInt(process.env.PORT || config.express.port || '8082');
    var host = process.env.HOST || config.express.host || 'localhost';
    var server = app.listen(port, host, function () {
        console.log("warehouse api service running on %s:%d in %s mode", host, port, app.settings.env);
    });
});

//increase timeout for dataset download .. (default 120s)
//without this, places like nki/s3 will timeout
//server.timeout = 300*1000; 