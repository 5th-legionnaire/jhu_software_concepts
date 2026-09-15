#!/bin/bash
# run_llm.sh — run the LLM standardizer over applicant_data.json in chunks.
#
# Chunking costs about 26 seconds of extra model loading across the whole run
# and makes the job resumable: rerunning skips any chunk whose output already
# exists, so a failure at record 28,000 costs one chunk, not the whole run.
#
# Run from module_2/llm_hosting with that venv active:
#     bash ../run_llm.sh

set -euo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHUNK_DIR="$MODULE_DIR/chunks"
CHUNK_SIZE=3000

export N_GPU_LAYERS=999
export N_BATCH=512

# --- 1. split applicant_data.json into chunks -----------------------------
mkdir -p "$CHUNK_DIR"
python3 - "$MODULE_DIR" "$CHUNK_DIR" "$CHUNK_SIZE" <<'PY'
import json, os, sys
module_dir, chunk_dir, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
records = json.load(open(os.path.join(module_dir, "applicant_data.json"), encoding="utf-8"))
for index in range(0, len(records), size):
    path = os.path.join(chunk_dir, f"chunk_{index // size:02d}.json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as out:
            json.dump(records[index:index + size], out, ensure_ascii=False)
print(f"{len(records)} records in {(len(records) + size - 1) // size} chunks")
PY

# --- 2. standardize each chunk, skipping ones already done ----------------
for chunk in "$CHUNK_DIR"/chunk_[0-9][0-9].json; do
    out="${chunk%.json}.out.json"
    if [ -s "$out" ]; then
        echo "skip $(basename "$chunk") (already done)"
        continue
    fi
    echo "running $(basename "$chunk")..."
    python3 app.py --file "$chunk" --stdout > "$out" 2> "${chunk%.json}.log"
done

# --- 3. stitch the chunk outputs back into one JSON array -----------------
python3 - "$CHUNK_DIR" "$MODULE_DIR/llm_extend_applicant_data.json" <<'PY'
import glob, json, os, sys
chunk_dir, final = sys.argv[1], sys.argv[2]
records = []
for path in sorted(glob.glob(os.path.join(chunk_dir, "chunk_[0-9][0-9].out.json"))):
    text = open(path, encoding="utf-8").read().strip()
    if not text:
        continue
    try:
        # The standardizer may emit a JSON array...
        records.extend(json.loads(text))
    except json.JSONDecodeError:
        # ...or one JSON object per line (JSONL).
        records.extend(json.loads(line) for line in text.splitlines() if line.strip())
with open(final, "w", encoding="utf-8") as out:
    json.dump(records, out, indent=2, ensure_ascii=False)
print(f"wrote {len(records)} records to {os.path.basename(final)}")
PY