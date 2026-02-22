import { spawn } from "node:child_process";

export interface SpawnResult {
  ok: boolean;
  runId: string;
  trace: string;
  final: string;
  artifacts: string;
  error?: { type: string; msg: string };
  summary: string;
}

export const runtime = {
  spawn: spawnPirml,
};

export async function spawnPirml(
  prog: string,
  outDir: string,
  artDir: string,
  timeoutMs: number = 60000
): Promise<SpawnResult> {
  const args = [
    "-m", "pirml",
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
          error: { type: "runtime", msg: err.trim() || `exit ${code}` },
          summary: "PIRML Run Failed",
        });
        return;
      }

      // Try to parse summary from out (it should be stdout from pirml)
      // Actually, we should probably read final.json or just derivation
      // For now, let's just return success and minimal summary
      resolve({
        ok: true,
        runId,
        trace,
        final,
        artifacts: artDir,
        summary: "PIRML Run OK",
      });
    });

    p.on("error", (e) => {
      clearTimeout(t);
      reject(e);
    });
  });
}
