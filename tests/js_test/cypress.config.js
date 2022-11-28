module.exports = {
  e2e: {
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    baseUrl: 'http://localhost:8080',
    specPattern: 'tests/js_test/cypress/e2e/test-*.js',
    fixturesFolder: false,
    supportFile: 'tests/js_test/cypress/support/e2e.js',
  },
};
