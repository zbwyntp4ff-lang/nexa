const fs = require("fs");
const path = process.argv[2];
const s = fs.readFileSync(path, "utf8");
const i = s.indexOf("current-password");
console.log("idx", i);
console.log(s.slice(Math.max(0, i - 600), i + 400));
console.log("inputMode", s.includes("inputMode"));
console.log("type email string", s.includes('type:"email"') || s.includes("type:'email'") || s.includes('type:\\"email\\"'));
console.log("type text near login", s.includes('type:"text"'));
