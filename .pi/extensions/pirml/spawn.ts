import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

export interface SpawnResult {
  ok: boolean;
  runId: string;
  trace: string;
  final: string;
  artifacts: string;
  runSha: string;
  error?: { type: string; msg: string };
  summary: string;
}

export interface DoctorResult {
  ok: boolean;
  code: number;
  stdout: string;
  stderr: string;
}

export const runtime = {
  spawn: spawnPirml,
  doctor: runDoctor,
};

export async function spawnPirml(
  prog: string,
  outDir: string,
  artDir: string,
  timeoutMs: number = 60000
): Promise<SpawnResult> {
  const args = [
    "-m", "scripts.pirml_run",
    "--prog", prog,
    "--out-dir", outDir,
    "--timeout", (timeoutMs / 1000).toString(),
  ];

  return new Promise((resolve, reject) => {
    const p = spawn("python", args, {
      cwd: process.cwd(),
      env: process.env,
    });

    let out = "";
    let err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));

    const t = setTimeout(() => {
      p.kill("SIGKILL");
    }, timeoutMs);

    p.on("close", (code) => {
      clearTimeout(t);
      
      const trace = `${outDir}/trace.ndjson`;
      const final = `${outDir}/final.json`;
      const runId = outDir.split("/").pop() || "unknown";

      if (code !== 0) {
        resolve({
          ok: false,
          runId,
          trace,
          final,
          artifacts: artDir,
          runSha: "",
          error: { type: "runtime", msg: err.trim() || `exit ${code}` },
          summary: "PIRML Run Failed",
        });
        return;
      }

      // Try to parse summary from out (it should be stdout from pirml)
      // Actually, we should probably read final.json or just derivation
      // For now, let's just return success and minimal summary
      readFinalSha(final)
        .then((runSha) =>
          resolve({
            ok: true,
            runId,
            trace,
            final,
            artifacts: artDir,
            runSha,
            summary: "PIRML Run OK",
          })
        )
        .catch((e) => reject(e));
    });

    p.on("error", (e) => {
      clearTimeout(t);
      reject(e);
    });
  });
}

async function readFinalSha(finalPath: string): Promise<string> {
  const bytes = await readFile(finalPath);
  return createHash("sha256").update(bytes).digest("hex");
}

function runDoctor(): Promise<DoctorResult> {
  return new Promise((resolve, reject) => {
    const p = spawn("python", ["-m", "pirml", "doctor"], {
      cwd: process.cwd(),
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    p.stdout.on("data", (d) => (stdout += d));
    p.stderr.on("data", (d) => (stderr += d));
    p.on("close", (code) => {
      resolve({
        ok: code === 0,
        code: code ?? 2,
        stdout,
        stderr,
      });
    });
    p.on("error", (e) => reject(e));
  });
}
