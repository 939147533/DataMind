import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const FONT = "Microsoft YaHei";
const ACCENT = "#0B5FFF";
const DARK = "#0B1830";
const INK = "#0F172A";
const MUTED = "#475569";
const LIGHT_LINE = "#E2E8F0";
const LIGHT_BG = "#F8FAFC";

const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function addSlide(bg = "#FFFFFF") {
  const slide = deck.slides.add();
  slide.background.fill = bg;
  return slide;
}

function addText(slide, name, text, pos, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position: pos,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: opts.fontSize ?? 16,
    bold: opts.bold ?? false,
    color: opts.color ?? INK,
    alignment: opts.alignment ?? "left",
    verticalAlignment: opts.verticalAlignment ?? "top",
    wrap: opts.wrap ?? "square",
    lineSpacing: opts.lineSpacing ?? 1.25,
  };
  return shape;
}

function addRect(slide, name, pos, opts = {}) {
  return slide.shapes.add({
    geometry: opts.round ? "roundRect" : "rect",
    name,
    position: pos,
    fill: opts.fill ?? LIGHT_BG,
    line: opts.line ?? { style: "solid", fill: LIGHT_LINE, width: 1 },
    borderRadius: opts.round ? (opts.borderRadius ?? "rounded-2xl") : undefined,
    shadow: opts.shadow ?? "shadow-none",
  });
}

function addHeader(slide, kicker, title, opts = {}) {
  addText(slide, "kicker", kicker, { left: 72, top: 40, width: 500, height: 24 }, {
    fontSize: 14, bold: true, color: ACCENT, wrap: "none",
  });
  addText(slide, "title", title, { left: 72, top: 66, width: 1100, height: 58 }, {
    fontSize: 35, bold: true, color: INK, wrap: "none",
  });
  addRect(slide, "title-accent", { left: 72, top: 130, width: 56, height: 5 }, {
    fill: ACCENT, line: { style: "solid", fill: "none", width: 0 },
  });
  if (opts.footer !== false) addFooter(slide);
}

function addFooter(slide) {
  addRect(slide, "footer-line", { left: 72, top: 676, width: 1136, height: 1 }, {
    fill: LIGHT_LINE, line: { style: "solid", fill: "none", width: 0 },
  });
  addText(slide, "footer-left", "DataMind · 数据库 Agent Web 应用", { left: 72, top: 686, width: 500, height: 18 }, {
    fontSize: 12, color: "#94A3B8", wrap: "none",
  });
  addText(slide, "footer-page", String(deck.slides.items.length), { left: 1108, top: 686, width: 100, height: 18 }, {
    fontSize: 12, color: "#94A3B8", alignment: "right", wrap: "none",
  });
}

function addBullets(slide, name, items, pos, opts = {}) {
  const shape = addText(slide, name, "", pos, opts);
  const paragraphs = items.map((item) => {
    if (typeof item === "string") {
      return {
        bulletCharacter: "•",
        marginLeft: 22,
        indent: -12,
        spaceBefore: opts.spaceBefore ?? 8,
        runs: [item],
      };
    }
    return {
      bulletCharacter: "•",
      marginLeft: 22,
      indent: -12,
      spaceBefore: opts.spaceBefore ?? 8,
      runs: [
        { run: item.lead, textStyle: { bold: true, color: opts.leadColor ?? INK } },
        { run: item.text, textStyle: { color: opts.textColor ?? MUTED } },
      ],
    };
  });
  shape.text.set(paragraphs);
  return shape;
}

function addTable(slide, name, values, pos, opts = {}) {
  const rows = values.length;
  const cols = values[0].length;
  const table = slide.tables.add({
    rows,
    columns: cols,
    left: pos.left,
    top: pos.top,
    width: pos.width,
    height: pos.height,
    values,
  });
  table.styleOptions = { headerRow: true, bandedRows: true, firstColumn: false };
  table.borders.assign({ style: "solid", fill: "#D7E2F0", width: 1 });
  for (let c = 0; c < cols; c++) {
    const cell = table.getCell(0, c);
    cell.fill = opts.headerFill ?? DARK;
    cell.text.style = {
      typeface: FONT,
      fontSize: opts.headerSize ?? 16,
      bold: true,
      color: "#FFFFFF",
      alignment: "left",
      verticalAlignment: "middle",
      insets: { top: 7, bottom: 7, left: 14, right: 14 },
    };
  }
  for (let r = 1; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cell = table.getCell(r, c);
      cell.text.style = {
        typeface: FONT,
        fontSize: opts.bodySize ?? 16,
        color: INK,
        alignment: "left",
        verticalAlignment: "middle",
        insets: { top: 6, bottom: 6, left: 14, right: 14 },
      };
    }
  }
  return table;
}

function setNotes(slide, lines) {
  slide.speakerNotes.textFrame.setText(lines);
  slide.speakerNotes.setVisible(true);
}

function arrow(slide, name, pos, color = ACCENT) {
  return slide.shapes.add({
    geometry: "rightArrow",
    name,
    position: pos,
    fill: color,
    line: { style: "solid", fill: "none", width: 0 },
    shadow: "shadow-none",
  });
}
