const fs = require('fs');
const path = require('path');
const p = 'node_modules/@testing-library/react/dist/act-compat.js';
const content = fs.readFileSync(p, 'utf8');
console.log(content);
