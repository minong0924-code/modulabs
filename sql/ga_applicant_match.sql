-- 내부 지원자 DB와 GA 데이터를 매칭하는 일별 쿼리
-- 파라미터: @target_date (DATE) - 처리할 지원 일자 (예: DATE '2026-10-28')

WITH internal_db AS (
  SELECT
    CAST(submitted_at AS TIMESTAMP) AS submitted_ts_kst,
    TIMESTAMP_SUB(CAST(submitted_at AS TIMESTAMP), INTERVAL 9 HOUR) AS submitted_ts_utc,
    FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', CAST(submitted_at AS TIMESTAMP)) AS submitted_at_seoul,
    uuid,
    name,
    apply_id,
    course,
    semester
  FROM `modulabs-ga-workspace.Modulabs_internal_DB.KDT_Daily_Apply`
  WHERE name IS NOT NULL
    AND DATE(CAST(submitted_at AS TIMESTAMP)) = @target_date
    AND course IN ('AI-AGENT','AI-DATA','PRIVATE-AI','RESEARCH','EGIGAE','EDATA','ELLM','ENGR')
),
all_traffic_info AS (
  SELECT
    user_pseudo_id,
    ARRAY_AGG(COALESCE(collected_traffic_source.manual_source, traffic_source.source) ORDER BY event_timestamp ASC LIMIT 1)[OFFSET(0)] AS first_source,
    ARRAY_AGG(COALESCE(collected_traffic_source.manual_medium, traffic_source.medium) ORDER BY event_timestamp ASC LIMIT 1)[OFFSET(0)] AS first_medium,
    ARRAY_AGG(COALESCE(collected_traffic_source.manual_campaign_name, traffic_source.name) ORDER BY event_timestamp ASC LIMIT 1)[OFFSET(0)] AS first_campaign,
    ARRAY_AGG((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'content') ORDER BY (CASE WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'content') IS NULL THEN 1 ELSE 0 END) ASC, event_timestamp ASC LIMIT 1)[OFFSET(0)] AS first_content,
    ARRAY_AGG((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'term') ORDER BY (CASE WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'term') IS NULL THEN 1 ELSE 0 END) ASC, event_timestamp ASC LIMIT 1)[OFFSET(0)] AS first_term
  FROM `modulabs-ga-workspace.analytics_373566527.events_*`
  WHERE _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', @target_date)
  GROUP BY user_pseudo_id
),
ga_events AS (
  -- 유저별/코스별로 가장 신뢰도 높은(시간이 빠른) 이벤트 1건만 추출
  SELECT
    user_pseudo_id,
    user_id,
    match_course_code,
    page_category,
    MIN(event_ts_utc) AS event_ts_utc,
    MIN(completed_time_seoul) AS completed_time_seoul
  FROM (
    SELECT
      user_pseudo_id,
      user_id,
      TIMESTAMP_MICROS(event_timestamp) AS event_ts_utc,
      FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', TIMESTAMP_MICROS(event_timestamp), 'Asia/Seoul') AS completed_time_seoul,
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_url,
      -- 코스 코드 매핑 (DB와 일치시키기 위함)
      CASE
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/engr%' THEN 'ENGR'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/research%' THEN 'RESEARCH'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/edata%' THEN 'EDATA'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/egigae%' THEN 'EGIGAE'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/ellm%' THEN 'ELLM'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/ai-data%' THEN 'AI-DATA'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/ai-agent%' THEN 'AI-AGENT'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/private-ai%' THEN 'PRIVATE-AI'
        ELSE 'ETC'
      END AS match_course_code,
      -- 화면 표시용 카테고리
      CASE
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/engr%' THEN '아이펠 엔지니어'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/research%' THEN '아이펠 리서처'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/edata%' THEN '재직자 데이터'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/egigae%' THEN '재직자 기획개발'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/ellm%' THEN '재직자 LLM'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/ai-data%' THEN 'AI데이터'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/ai-agent%' THEN 'AI에이전트'
        WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') LIKE '%/private-ai%' THEN 'PRIVATE-AI'
        ELSE '기타'
      END AS page_category
    FROM `modulabs-ga-workspace.analytics_373566527.events_*`
    WHERE _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', @target_date)
      AND event_name = 'Apply_step2'
  )
  GROUP BY 1, 2, 3, 4
)

-- 최종 조인 (지원자 1명당 1행으로 중복 제거)
SELECT
    db.submitted_at_seoul AS db_submitted_at,
    db.apply_id,
    db.name,
    db.course,
    db.semester,
    COALESCE(t.first_source, 'direct') AS session_source,
    COALESCE(t.first_medium, '(none)') AS session_medium,
    COALESCE(t.first_campaign, '(not set)') AS session_campaign,
    COALESCE(t.first_content, '(not set)') AS session_content,
    COALESCE(t.first_term, '(not set)') AS session_term
FROM internal_db AS db
LEFT JOIN ga_events AS e
  ON (
      (db.uuid IS NOT NULL AND CAST(db.uuid AS STRING) = CAST(e.user_id AS STRING))
      OR
      (db.uuid IS NULL AND ABS(TIMESTAMP_DIFF(db.submitted_ts_utc, e.event_ts_utc, SECOND)) <= 10)
  )
  -- DB의 course와 GA의 match_course_code가 일치할 때만 연결
  AND db.course = e.match_course_code
LEFT JOIN all_traffic_info AS t ON e.user_pseudo_id = t.user_pseudo_id
-- 한 지원자가 여러 GA 사용자와 연결되면 매칭 정보가 있는 행을 우선 선택
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY db.apply_id
  ORDER BY (e.user_pseudo_id IS NULL), e.event_ts_utc
) = 1
ORDER BY db.course DESC, db_submitted_at ASC;
