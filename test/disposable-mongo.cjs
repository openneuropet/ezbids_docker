// Validate the actual database path, not a suffix that could occur in a query
// string for a completely different database.
module.exports = function disposableMongoUri(uri) {
    const parsed = new URL(uri);
    if (
        !['mongodb:', 'mongodb+srv:'].includes(parsed.protocol) ||
        decodeURIComponent(parsed.pathname) !== '/ezbids_auth_test' ||
        [...parsed.searchParams.keys()].some((key) => key.toLowerCase() === 'dbname')
    ) {
        throw new Error('Test database must be explicitly named ezbids_auth_test');
    }
    return uri;
};
