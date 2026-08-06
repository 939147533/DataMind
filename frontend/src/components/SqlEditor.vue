<template>
  <div ref="host" class="sql-editor"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { sql, StandardSQL } from "@codemirror/lang-sql";
import { defaultHighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { Compartment, EditorState } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";
import { drawSelection, EditorView, highlightActiveLine, keymap, lineNumbers } from "@codemirror/view";
import { useSettingsStore } from "../stores/settings";

const props = defineProps<{ modelValue: string }>();
const emit = defineEmits<{ (e: "update:modelValue", v: string): void }>();
const host = ref<HTMLElement>();
const settings = useSettingsStore();
let view: EditorView | null = null;
const themeCompartment = new Compartment();
const fontSizeCompartment = new Compartment();

function fontSizeTheme() {
  const size = `${settings.editor_font_size || 14}px`;
  return EditorView.theme({ "&": { fontSize: size } });
}

function buildExtensions() {
  return [
    lineNumbers(),
    history(),
    drawSelection(),
    highlightActiveLine(),
    EditorState.allowMultipleSelections.of(true),
    keymap.of([...defaultKeymap, ...historyKeymap, ...closeBracketsKeymap, ...completionKeymap, indentWithTab]),
    autocompletion(),
    closeBrackets(),
    syntaxHighlighting(defaultHighlightStyle),
    sql({ dialect: StandardSQL }),
    themeCompartment.of(settings.isDark ? oneDark : []),
    fontSizeCompartment.of(fontSizeTheme()),
    EditorView.updateListener.of((u) => {
      if (u.docChanged) emit("update:modelValue", u.state.doc.toString());
    }),
    EditorView.lineWrapping,
  ];
}

onMounted(() => {
  if (!host.value) return;
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({ doc: props.modelValue, extensions: buildExtensions() }),
  });
});

watch(
  () => props.modelValue,
  (val) => {
    if (view && view.state.doc.toString() !== val) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: val } });
    }
  },
);

watch(
  () => [settings.isDark, settings.editor_font_size] as const,
  () => {
    if (!view) return;
    view.dispatch({ effects: [themeCompartment.reconfigure(settings.isDark ? oneDark : []), fontSizeCompartment.reconfigure(fontSizeTheme())] });
  },
);

onBeforeUnmount(() => {
  view?.destroy();
  view = null;
});
</script>

<style scoped>
.sql-editor {
  height: 100%;
  min-height: 140px;
  overflow: hidden;
}
.sql-editor :deep(.cm-editor) {
  height: 100%;
}
</style>
