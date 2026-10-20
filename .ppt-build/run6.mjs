import("./build6.mjs").catch(e => { console.log("ERR_NAME:", e && e.name); console.log("ERR_MSG:", String(e && e.message).split("\n")[0].slice(0, 500)); });
