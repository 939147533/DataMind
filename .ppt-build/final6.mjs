import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";

const SRC = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx";
const DRAFT = "/Users/ly/Code/DataMind/.ppt-build/draft-v13.pptx";
const SHOULD_FINALIZE = process.argv.includes("--finalize");

const SKILL_DIR = "/Users/ly/.codex/plugins/cache/openai-primary-runtime/presentations/26.1013.11914/skills/presentations";
const workspaceDir = "/Users/ly/Code/DataMind";
const RUNTIME_PYTHON = "/Users/ly/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const FINAL_PPTX = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.3.pptx";

const presentation = await PresentationFile.importPptx(await FileBlob.load(DRAFT));
const requirements = {
  explicitTotalSlideCount: 27,
  requiredNativeTableOwnerSlides: [17, 19, 27],
  requiredNativeChartOwnerSlides: [],
};
const fontPolicy = {
  basis: "reference",
  families: ["Helvetica Neue", "微软雅黑"],
  referencePath: SRC,
  referenceSha256: "45fab91ae647da211e74a01dfb261d9bb58cc8be107e7e81b02d4650caed80b6",
};

if (!SHOULD_FINALIZE) {
  console.log("dry run: requirements", JSON.stringify(requirements), "fontPolicy", JSON.stringify(fontPolicy));
  process.exit(0);
}

const { finalizePresentation } = await import(pathToFileURL(
  path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs"),
).href);
const stagingDir = path.join(workspaceDir, ".ppt-build/finalizer");
await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const candidatePath = path.join(stagingDir, "candidate-v13.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const tableOwners = requirements.requiredNativeTableOwnerSlides;
const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
    ...tableOwners.flatMap((number) => ["--require-native-table-slide", String(number)]),
  ],
  requiredNativeTableOwnerSlides: tableOwners,
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "final-v13.validation.json"),
});
console.log("FINAL", FINAL_PPTX);
console.log(JSON.stringify(result, null, 1).slice(0, 6000));
