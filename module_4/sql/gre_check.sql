--This is a SQL query used to check GRE values in the database.

SELECT metric, bucket, COUNT(*) FROM (
  SELECT 'gre' AS metric,
         CASE WHEN gre < 130 THEN '1: <130'   WHEN gre <= 170 THEN '2: 130-170'
              WHEN gre < 260 THEN '3: 171-259' WHEN gre <= 340 THEN '4: 260-340'
              ELSE '5: >340' END AS bucket
  FROM applicants WHERE gre IS NOT NULL
  UNION ALL
  SELECT 'gre_v', CASE WHEN gre_v < 130 THEN '1: <130' WHEN gre_v <= 170 THEN '2: 130-170'
                       ELSE '3: >170' END
  FROM applicants WHERE gre_v IS NOT NULL
  UNION ALL
  SELECT 'gre_aw', CASE WHEN gre_aw < 0 THEN '1: <0' WHEN gre_aw <= 6 THEN '2: 0-6'
                        ELSE '3: >6' END
  FROM applicants WHERE gre_aw IS NOT NULL
  UNION ALL
  SELECT 'gpa', CASE WHEN gpa <= 0 THEN '1: <=0' WHEN gpa <= 4.0 THEN '2: 0-4.0'
                     WHEN gpa <= 4.33 THEN '3: 4.0-4.33' WHEN gpa <= 10 THEN '4: 4.33-10'
                     ELSE '5: >10' END
  FROM applicants WHERE gpa IS NOT NULL
) t GROUP BY 1, 2 ORDER BY 1, 2;