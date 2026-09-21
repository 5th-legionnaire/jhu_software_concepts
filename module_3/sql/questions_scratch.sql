--This query is to determine why both q8 and q8 are returning the same results. The issue is that the original query is using the "degree" field, which is not being populated for LLM applicants. Therefore, the query is returning the same results for both q8 and q9.
SELECT (program ~* 'computer science'
        AND program ~* 'georgetown|massachusetts institute of technology|\mmit\M|stanford|carnegie mellon|\mcmu\M') AS original_match,
       (llm_generated_program ~* 'computer science'
        AND llm_generated_university ~* 'georgetown|massachusetts institute of technology|\mmit\M|stanford|carnegie mellon|\mcmu\M') AS llm_match,
       COUNT(*)
FROM applicants
WHERE LOWER(term) = 'fall 2026' AND LOWER(status) = 'accepted' AND LOWER(degree) = 'phd'
GROUP BY 1, 2 ORDER BY 1, 2;