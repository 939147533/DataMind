import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const t = await p.inspect({ select: "$.slides[*]", include: ["index","elements.id","elements.kind","elements.text"] });
const rows = t.records.slice().sort((a,b)=>a.index-b.index);
const show = (idx, id) => { const r=rows.find(x=>x.index===idx); const e=(r.elements||[]).find(x=>x.id===id); console.log(`p${idx+1} ${id}:`, JSON.stringify(e?.text)); };
show(7,"sh/tkby9kzm");
show(13,"sh/c3e1gjyd");
show(19,"sh/rid4nuhs");
show(20,"sh/ixsf2d87");
show(20,"sh/jy1gbi9s");
show(20,"sh/0f2lon6p");
// table dims
const r17 = rows.find(r=>r.index===16);
const tbEl = (r17.elements||[]).find(e=>e.kind==="table");
console.log("table text:", JSON.stringify(tbEl.text));
const tb = p.resolve(tbEl.id);
try { console.log("rows prop:", tb.rows, "cols prop:", tb.columns); } catch(e){ console.log("rows prop err:", e.message.slice(0,80)); }
try { console.log("cell(0,0):", JSON.stringify(tb.getCell(0,0).value)); } catch(e){ console.log("getCell err:", e.message.slice(0,100)); }
for (let r=0;r<8;r++){ try { const v = tb.getCell(r,0).value; console.log("row",r,"col0 =", JSON.stringify(String(v).slice(0,40))); } catch(e){ console.log("row",r,"out of range"); } }
