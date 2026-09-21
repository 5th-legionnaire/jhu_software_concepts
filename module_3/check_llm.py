"""Compare the LLM's standardized university against the parsed one."""
import json
from collections import Counter

"Load the records saved by clean_data() and compare the LLM's standardized university against the parsed one."
records = json.load(open("llm_extend_applicant_data.json", encoding="utf-8"))
print(f"records: {len(records)}")
print(f"unique urls: {len({r['url'] for r in records})}")

"Compute the number of exact matches and the top mismatches."
key = "llm-generated-university"
scored = [r for r in records if r.get(key)]
hits = sum(1 for r in scored if r[key] == r["university"])
print(f"exact university match: {hits}/{len(scored)} ({100 * hits / len(scored):.1f}%)")

misses = Counter(
    (r["university"], r[key]) for r in scored if r[key] != r["university"]
)
print("\ntop mismatches:")
for (parsed, llm), count in misses.most_common(25):
    print(f"  {count:5}  {parsed!r} -> {llm!r}")