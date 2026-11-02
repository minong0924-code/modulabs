# Modulabs / AIFFEL 플랫폼 — 전체 데이터베이스 스키마 레퍼런스

> 외부 팀 에이전트용 단일 컨텍스트 파일. 모든 테이블의 컬럼, 타입, 관계 정보 포함.
> 생성일: 2026-04-10

---

## 목차

1. [시스템 구성 개요](#1-시스템-구성-개요)
2. [PostgreSQL 커넥션 구성](#2-postgresql-커넥션-구성)
3. [Base 모델 (TypeORM)](#3-base-모델-typeorm)
4. [NestJS 엔티티 — service 스키마](#4-nestjs-엔티티--service-스키마)
5. [NestJS 엔티티 — public 스키마 (레거시 공유)](#5-nestjs-엔티티--public-스키마)
6. [NestJS 엔티티 — orderx 스키마](#6-nestjs-엔티티--orderx-스키마)
7. [NestJS 엔티티 — resource 스키마](#7-nestjs-엔티티--resource-스키마)
8. [NestJS 엔티티 — class 스키마](#8-nestjs-엔티티--class-스키마)
9. [NestJS 엔티티 — membership 스키마](#9-nestjs-엔티티--membership-스키마)
10. [NestJS 엔티티 — biz 스키마](#10-nestjs-엔티티--biz-스키마)
11. [NestJS 엔티티 — channeltalk 스키마](#11-nestjs-엔티티--channeltalk-스키마)
12. [NestJS 엔티티 — section 스키마](#12-nestjs-엔티티--section-스키마)
13. [NestJS 엔티티 — vod 스키마](#13-nestjs-엔티티--vod-스키마)
14. [NestJS 엔티티 — 기타](#14-nestjs-엔티티--기타)
15. [Django 모델 (aiffel_back)](#15-django-모델-aiffel_back)
16. [Redis / MySQL 구성](#16-redis--mysql-구성)
17. [사용자 역할 체계](#17-사용자-역할-체계)
18. [수강 상태 코드 (core_courseprogrs)](#18-수강-상태-코드)
19. [데이터 접근 패턴](#19-데이터-접근-패턴)
20. [환경별 DB 호스트](#20-환경별-db-호스트)

---

## 1. 시스템 구성 개요

```
modulabs-backend-service (NestJS 10, TypeORM 0.3)
  ├── PostgreSQL (4개 커넥션: default, vod, orderx, resource)
  ├── Redis Cluster (캐시/세션/분산 락)
  └── MySQL (분산 락 폴백)

aiffel_back (Django 3.2, DRF)
  ├── PostgreSQL (단일 커넥션)
  ├── Redis + Celery (27개 백그라운드 태스크)
  └── AWS 서비스 연동 (S3, SES, SNS, SQS, Bedrock)

* dev/stg: NestJS와 Django가 동일 PostgreSQL 인스턴스 공유 가능
* prd: 별도 인스턴스
* Timezone: Asia/Seoul
```

---

## 2. PostgreSQL 커넥션 구성

| 커넥션명 | Database | Schema | 용도 | 풀 사이즈 |
|----------|----------|--------|------|-----------|
| **default** | `postgres` | `service` | 핵심 비즈니스 로직 | 15 |
| **vod** | `vod` | `public` | 비디오 콘텐츠 | 5 |
| **orderx** | `postgres` | `orderx` | 주문/결제/쿠폰 | 7 |
| **resource** | `postgres` | `resource` | JupyterHub/GCP 리소스 | 7 |

**추가 스키마**: `membership`, `class`, `biz`, `channeltalk`, `section` (모두 default 커넥션)

---

## 3. Base 모델 (TypeORM)

### ModulabsBaseModel (대부분의 엔티티가 상속)
| 컬럼 | 타입 | 제약조건 |
|------|------|---------|
| id | int8 | PK, auto-increment (StringToNumberTransformer) |
| createdAt | timestamptz | NOT NULL, update:false, default: CURRENT_TIMESTAMP |
| modifiedAt | timestamptz | NOT NULL, default: CURRENT_TIMESTAMP |

### ModulabsUUIDBaseEntity (UUID PK 사용 엔티티)
| 컬럼 | 타입 | 제약조건 |
|------|------|---------|
| id | varchar | PK (UUID, BeforeInsert 자동생성) |
| createdAt | Date | NOT NULL, update:false |
| modifiedAt | Date | NOT NULL |

**공통 참고**: `@IdColumn()` = `@Column({ type: 'bigint', transformer: StringToNumberTransformer })`
**네이밍**: SnakeNamingStrategy (DB컬럼 snake_case, 코드 camelCase)

---

## 4. NestJS 엔티티 — service 스키마

> **259+ 엔티티**. service 스키마는 핵심 비즈니스 로직을 담당하며 100+ 테이블로 구성.

### 사용자 & 인증

| 테이블 | 설명 |
|--------|------|
| `auth_member` | 회원 기본 정보 |
| `auth_member_login_history` | 로그인 이력 |
| `auth_member_login_method` | 로그인 수단 (이메일, 소셜 등) |
| `auth_member_privacy` | 개인정보 |
| `auth_member_profile` | 프로필 정보 |
| `auth_member_referral` | 추천인 정보 |

### 강좌 콘텐츠 (코어)

| 테이블 | 설명 |
|--------|------|
| `core_course` | 강좌 |
| `core_node` | 학습 노드 (강좌의 하위 단위) |
| `core_nodeversion` | 노드 버전 관리 |
| `core_subject` | 과목 |
| `core_enrol` | 수강 등록 |
| `core_evaluation` | 평가 |
| `core_rubric` | 평가 기준 (루브릭) |
| `core_step` | 학습 단계 |
| `core_coursenodeversionrelation` | 강좌-노드버전 관계 매핑 |

### 학습 진도

| 테이블 | 설명 |
|--------|------|
| `core_nodeprogrs` | 노드별 진도 |
| `core_learning_time` | 학습 시간 기록 |
| `core_stepcompt` | 단계 완료 |

### 멤버십 & 그룹

| 테이블 | 설명 |
|--------|------|
| `member_group` | 회원 그룹 |
| `member_group_mapping` | 그룹-회원 매핑 |
| `user_group` | 사용자 그룹 |
| `user_group_course_mapping` | 사용자그룹-강좌 매핑 |

### 커뮤니티

| 테이블 | 설명 |
|--------|------|
| `post` | 게시글 |
| `board` | 게시판 |
| `comment` | 댓글 |
| `notice` | 공지사항 |
| `chat_room` | 채팅방 |
| `chat_message` | 채팅 메시지 |

### 관리 & 알림

| 테이블 | 설명 |
|--------|------|
| `admin_action_history` | 관리자 액션 이력 |
| `alimtalk_notification_history` | 카카오 알림톡 발송 이력 |
| `slack_info` | Slack 연동 정보 |
| `push_notification` | 푸시 알림 |

### 정산 & 분석

| 테이블 | 설명 |
|--------|------|
| `settlement_request` | 정산 요청 |
| `settlement_history` | 정산 이력 |
| `momo` | 모모 (스터디 그룹) |
| `momo_settlement` | 모모 정산 |

> NestJS 엔티티 상세 컬럼 정보는 소스 코드의 `src/` 하위 각 모듈의 `*.entity.ts` 파일 참조.
> 엔티티 파일 위치: `src/course/entity/`, `src/orderx/entities/`, `src/membership/entities/`, `src/resource/entities/`, `src/lab/meta/entities/`, `src/product/entities/` 등 약 50개 모듈에 분산.

---

## 5. NestJS 엔티티 — public 스키마

Django(aiffel_back)와 NestJS 양쪽에서 접근 가능한 레거시 테이블.

| 테이블 | 설명 |
|--------|------|
| `core_courseprogrs` | 수강 상태 (상태코드 A~S, 섹션 18 참고) |
| `core_userenrolments` | 사용자-강좌 수강 등록 |
| `core_usersubmission` | 학생 제출물 |
| `core_userlogentry` | 활동 로그 |
| `core_file` | 강좌 파일 |
| `apply_order` | 신청 주문 |
| `apply_applicationform` | 신청 양식 |
| `apply_coursesemester` | 강좌 기수 |
| `order_order` | 레거시 주문 |
| `order_orderitem` | 레거시 주문 항목 |
| `order_ordertransaction` | 레거시 결제 트랜잭션 |

---

## 6. NestJS 엔티티 — orderx 스키마

9 테이블. 주문/결제/쿠폰 도메인.

| 테이블 | 설명 |
|--------|------|
| `order` | 주문 (PK: `order_pk` string) |
| `order_item` | 주문 항목 |
| `order_member` | 주문 회원 정보 |
| `order_transaction` | 결제 트랜잭션 |
| `cart` | 장바구니 |
| `cart_item` | 장바구니 항목 |
| `coupon` | 쿠폰 |
| `coupon_member` | 쿠폰-회원 매핑 |
| `coupon_member_history` | 쿠폰 사용 이력 |
| `webhook_history` | PG 웹훅 이력 |

---

## 7. NestJS 엔티티 — resource 스키마

13+ 테이블. JupyterHub/GCP 리소스 관리.

| 테이블 | 설명 |
|--------|------|
| `jupyter_hub` | JupyterHub 인스턴스 |
| `jupyter_server` | Jupyter 서버 |
| `jupyter_user` | Jupyter 사용자 |
| `jupyter_user_token` | Jupyter 사용자 토큰 |
| `instance` | GCP 인스턴스 |
| `instance_template` | 인스턴스 템플릿 |
| `instance_group` | 인스턴스 그룹 |
| `disk` | GCP 디스크 |
| `user_instance` | 사용자-인스턴스 매핑 |
| `user_disk` | 사용자-디스크 매핑 |
| `user_resource` | 사용자 리소스 |
| `gcp_operation` | GCP 오퍼레이션 로그 |
| `jupyter_server_event_log` | Jupyter 서버 이벤트 로그 |
| `user_instance_access_log` | 인스턴스 접근 로그 |
| `lms_user_report` | LMS 사용자 리포트 |

---

## 8. NestJS 엔티티 — class 스키마

13+ 테이블. B2B 클래스 관리.

| 테이블 | 설명 |
|--------|------|
| `class` | B2B 클래스 |
| `class_creator` | 클래스 생성자 |
| `class_order_enrol` | 클래스 주문-수강 매핑 |
| `class_review` | 클래스 리뷰 |
| 기타 클래스 관련 테이블 | 클래스 스케줄, 참여자, 권한 등 |

---

## 9. NestJS 엔티티 — membership 스키마

회원 멤버십/로그인 관련 테이블.

| 테이블 | 설명 |
|--------|------|
| 멤버십 상태 테이블 | 멤버십 상태 관리 |
| 로그인 데이터 테이블 | 로그인 관련 데이터 |

---

## 10. NestJS 엔티티 — biz 스키마

B2B 주문 관련 테이블.

| 테이블 | 설명 |
|--------|------|
| 비즈 클래스 주문 테이블 | B2B 기업교육 주문 관리 |

---

## 11. NestJS 엔티티 — channeltalk 스키마

고객 지원 채널톡 연동 테이블.

| 테이블 | 설명 |
|--------|------|
| 채널톡 데이터 테이블 | 채널톡 연동 데이터 저장 |

---

## 12. NestJS 엔티티 — section 스키마

콘텐츠 섹션 구조 관련 테이블.

| 테이블 | 설명 |
|--------|------|
| 섹션 구조 테이블 | 콘텐츠 섹션 관리 |

---

## 13. NestJS 엔티티 — vod 스키마

비디오 콘텐츠 관리 (vod 커넥션, public 스키마).

| 테이블 | 설명 |
|--------|------|
| VOD 관련 테이블 | 비디오 콘텐츠 및 메타데이터 관리 |

---

## 14. NestJS 엔티티 — 기타

기타 스키마에 속하지 않는 엔티티.

| 카테고리 | 주요 엔티티 |
|----------|------------|
| Lab/Meta | `lab_meta` 등 4개 엔티티 |
| Product | `product` 등 1개 엔티티 |

---

## 15. Django 모델 (aiffel_back)

> **93개 concrete 모델** + 4개 proxy 모델 + 1개 abstract 클래스 + 2개 Wagtail Page 모델.
> 14개 앱 파일에 분산.

### apply app

#### apply.apply_applicationform (ApplicationForm)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| name | CharField(max_length=10) | NULL, blank, db_index | 이름 |
| name_chosung | CharField(max_length=10) | NULL, blank, db_index | 이름 초성 |
| email | EmailField | NULL, blank, validate_email | |
| member_id | BigIntegerField | NULL, blank | |
| member_uuid | CharField(max_length=255) | NULL, blank | |
| phone_number | CharField(max_length=13) | NULL, blank, regex: ^010-?\d{4}-?\d{4}$ | |
| birth | DateField | NULL, blank | |
| course | CharField(max_length=30) | NULL, blank | |
| introduction | TextField | NULL, blank, default='' | |
| admin_note | TextField | NULL, blank | |
| additional_note | TextField | NULL, blank | |
| nb_card_yn | BooleanField | NULL, blank | 내일배움카드 여부 |
| support_path | CharField(max_length=100) | NULL, blank | |
| application_form_check_yn | BooleanField | NULL, default=None | |
| application_form_pass_yn | BooleanField | NULL, default=None | |
| interview_guide_yn | BooleanField | NULL, default=None | |
| interview_reserve_yn | BooleanField | NULL, default=None | |
| interview_attend_yn | BooleanField | NULL, default=None | |
| interview_pass_yn | BooleanField | NULL, default=None | |
| admission_step | IntegerField | default=0 | choices: ADMISSION_STEP_CHOICES |
| status | CharField(max_length=2) | default='0', db_index | choices: STATUS_CHOICES |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |
| interview_date | DateTimeField | NULL, blank | |
| interview_link | URLField(max_length=500) | NULL, blank | |
| online_semester | IntegerField | default=5 | |
| term_agreement_yn | BooleanField | NULL, blank | |
| mkt_agreement_yn | BooleanField | NULL, blank | |
| portfolio_link | URLField(max_length=500) | NULL, blank | |
| last_modifier_id | ForeignKey | NULL, CASCADE | |
| major | CharField(max_length=400) | NULL, blank | |
| status_check | CharField(max_length=100) | NULL, blank | |
| fail_reason | CharField(max_length=100) | NULL, blank | |
| give_up_reason | CharField(max_length=100) | NULL, blank | |
| send_msg_flag | BooleanField | default=True | |
| submitted_at | DateTimeField | NULL, blank | 서류 제출 시간 |
| document_reviewed_at | DateTimeField | NULL, blank | 서류 검토 완료 시간 |
| document_result_at | DateTimeField | NULL, blank | 서류 합/불 결과 시간 |
| interview_guided_at | DateTimeField | NULL, blank | 면접 안내된 시간 |
| interview_reserved_at | DateTimeField | NULL, blank | 면접 예약된 시간 |
| interview_attended_at | DateTimeField | NULL, blank | 면접 참석/미참석 시간 |
| interview_result_at | DateTimeField | NULL, blank | 면접 합/불 결과 시간 |
| final_result_at | DateTimeField | NULL, blank | 최종 결과 시간 |
| extra_answer | JSONField | NULL, blank | |
| extra_origin_answer | JSONField | NULL, blank | |
| application_form_template_id | ForeignKey | NULL, blank, SET_NULL | |

**관계:**
- last_modifier -> ForeignKey(AUTH_USER_MODEL, on_delete=CASCADE)
- application_form_template -> ForeignKey(ApplicationFormTemplate, on_delete=SET_NULL)

**Choices:**
- status: 0=작성중, 1=지원서 1단계 제출, 2=지원서 2단계 제출 완료, 3=서류 검토 완료, 4a=서류 합격, 4b=서류 불합격, 5=면접 안내 완료, 5a=면접 예약 완료, 5b=면접 예약 취소, 6a=면접 참석, 6b=면접 미참석, 7a=면접 합격, 7b=면접 불합격, 8a=최종 입학, 8b=최종 불합격, 8c=수강 포기
- admission_step: 0=미입력, 1=최종 입학, 2=불합격, 3=수강 포기

**Meta:** ordering = [Case(submitted_at desc, fallback created_at desc)]; HistoricalRecords 활성

---

#### apply.apply_applicationformstep2 (ApplicationFormStep2)

**파일**: `apply/models.py`
**상속**: TimeStampedModel (created, modified)

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| application_form_id | ForeignKey | NOT NULL, CASCADE | |
| emergency_contact | CharField(max_length=13) | NOT NULL, regex: ^010-?\d{4}-?\d{4}$ | |
| emergency_contact_relationship | CharField(max_length=10) | NULL, blank | |
| address | CharField(max_length=500) | NOT NULL | |
| resident_registration_number | BinaryField | NOT NULL | 주민등록번호 (암호화) |
| training_participation_type | CharField(max_length=255) | NOT NULL | choices: TRAINING_TYPES_CHOICES |
| last_degree | CharField(max_length=255) | NOT NULL | choices: EDUCATION_LEVELS_CHOICES |
| education_department | CharField(max_length=255) | NULL, blank | choices: EDUCATION_DEPARTMENTS_CHOICES |
| major | CharField(max_length=60) | NULL, blank | |
| current_major | CharField(max_length=60) | NULL, blank | |
| undergraduate_major | CharField(max_length=60) | NULL, blank | |
| economic_activity_experience_yn | BooleanField | default=False | |
| economic_activity_experience_period | CharField(max_length=20) | NULL, blank | choices |
| economic_activity_experience_detail | TextField | NULL, blank | |
| goals_after_completing_aiffel | CharField(max_length=30) | NOT NULL | choices |
| ai_related_learning_experience | CharField(max_length=100) | NOT NULL | choices |
| ai_related_project_experience | TextField | NOT NULL | |
| programming_languages_and_frameworks | CharField(max_length=300) | NULL, blank | |
| preferred_ai_learning_field | CharField(max_length=50) | NULL, blank | |
| preferred_industry_group | CharField(max_length=120) | NULL, blank | |
| preferred_field_of_work | CharField(max_length=300) | NULL, blank | |
| qualifications | TextField | NULL, blank | |
| message_to_aiffel | TextField | NULL, blank | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- application_form -> ForeignKey(ApplicationForm, on_delete=CASCADE, related_name='application_form_step2')

---

#### apply.apply_trainee (Trainee)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| hrd_information_id | ForeignKey | NOT NULL, CASCADE, db_index | |
| trainee_code | CharField(max_length=255) | NOT NULL | |
| birth | DateField | NOT NULL | |
| name | CharField(max_length=10) | NOT NULL, db_index | |

**관계:**
- hrd_information -> ForeignKey(core.HrdInformation, on_delete=CASCADE, related_name='trainees')

**Meta:** ordering = [hrd_information, trainee_code]; unique_together = (hrd_information, trainee_code)

---

#### apply.apply_trainingstatus (TrainingStatus)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| trainee_id | ForeignKey | NOT NULL, CASCADE, db_index | |
| trainee_status | CharField(max_length=255) | NOT NULL | |
| total_attendance_days | IntegerField | NOT NULL | |
| total_absent_days | IntegerField | NOT NULL | |
| total_training_days | PositiveIntegerField | NOT NULL | |
| total_vacation_days | IntegerField | NOT NULL | |

**관계:**
- trainee -> ForeignKey(Trainee, on_delete=CASCADE)

**Meta:** unique_together = (trainee,)

---

#### apply.apply_trainingattendance (TrainingAttendance)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| trainee_id | ForeignKey | NOT NULL, CASCADE, db_index | |
| attendance_date | DateField | NOT NULL | |
| attendance_day | CharField(max_length=255) | NOT NULL | |
| attendance_status | CharField(max_length=255) | NOT NULL | |
| check_in_time | TimeField | NULL | |
| check_out_time | TimeField | NULL | |

**관계:**
- trainee -> ForeignKey(Trainee, on_delete=CASCADE)

**Meta:** ordering = [trainee, attendance_date]; unique_together = (trainee, attendance_date)

---

#### apply.apply_coursesemester (CourseSemester)

**파일**: `apply/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| course | CharField(max_length=255) | NOT NULL | choices: COURSE_CHOICES |
| semester | PositiveIntegerField | NOT NULL | |
| start_date | DateField | NOT NULL | 모집 시작일 |
| end_date | DateField | NOT NULL | 모집 종료일 |
| course_start_date | DateField | NULL, blank | 수강 시작일 |
| course_end_date | DateField | NULL, blank | 수강 종료일 |
| is_active | BooleanField | default=True | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**Choices:**
- course: CORE=코어, RESEARCH=리서치, SOCAR=쏘카, DS=데이터 사이언티스트, FULLSTACK=자바스크립트 웹 풀스택, FLUTTER=플러터, LLM=인공지능(AI) 모델 활용 백엔드 개발, ELLM=AI/LLM 서비스 개발 과정, TESTELLM=테스트-AI/LLM 서비스 개발 과정, TESTFULLSTACK=테스트-프론트엔드 개발(풀스택)

**Meta:** ordering = [course, semester]; unique_together = (course, semester)

---

#### apply.apply_coursegroup (CourseGroup)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| code | CharField(max_length=20) | UNIQUE | 과정 그룹 코드 |
| name | CharField(max_length=50) | NOT NULL | 과정 그룹명 |
| description | TextField | blank | 설명 |
| order | PositiveSmallIntegerField | default=0 | |
| is_active | BooleanField | default=True | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

**Meta:** verbose_name='과정 그룹'; ordering = [order, code]

---

#### apply.apply_coursetype (CourseType -- apply app)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| code | CharField(max_length=20) | UNIQUE | 과정 코드 |
| name | CharField(max_length=50) | NOT NULL | 과정명 |
| main_title | CharField(max_length=100) | NULL, blank | 메인(상위) 타이틀 |
| description | TextField | blank | 설명 |
| course_group_id | ForeignKey | NULL, blank, PROTECT | |
| localschool_id | ForeignKey | NULL, blank, CASCADE | |
| order | PositiveSmallIntegerField | default=0 | |
| is_active | BooleanField | default=True | |
| is_display | BooleanField | default=True | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

**관계:**
- course_group -> ForeignKey(CourseGroup, on_delete=PROTECT, related_name='course_types')
- localschool -> ForeignKey(core.LocalSchool, on_delete=CASCADE, related_name='course_types')

**Meta:** verbose_name='과정 유형'; ordering = [course_group, order, code]

---

#### apply.apply_coursemessagetemplate (CourseMessageTemplate)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| course_type_id | ForeignKey | NOT NULL, PROTECT | |
| apply_step_status | CharField(max_length=100) | NOT NULL | 상태 코드 (예: 4a, 4b, 7a, 7b) |
| apply_step_title | CharField(max_length=100) | NOT NULL | |
| template_id | CharField(max_length=100) | NOT NULL | |
| pf_id | CharField(max_length=100) | NOT NULL | |
| description | CharField(max_length=100) | NOT NULL | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

**관계:**
- course_type -> ForeignKey(CourseType, on_delete=PROTECT, related_name='message_templates')

---

#### apply.apply_coursemessagevariable (CourseMessageVariable)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| template_id | ForeignKey | NOT NULL, CASCADE | |
| key | CharField(max_length=50) | NOT NULL | |
| value | TextField | NOT NULL | |
| description | CharField(max_length=200) | blank | |
| content_type | CharField(max_length=20) | default='message' | choices |

**관계:**
- template -> ForeignKey(CourseMessageTemplate, on_delete=CASCADE, related_name='variables')

**Choices:**
- content_type: url=URL, message=메시지, word=단어, guide=안내문

**Meta:** unique_together = (template, key)

---

#### apply.apply_coursemessageschedule (CourseMessageSchedule)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| template_id | OneToOneField | NOT NULL, CASCADE | |
| schedule_type | CharField(max_length=20) | NOT NULL | 발송 스케줄 유형 |
| send_hour | IntegerField | NULL, blank | 발송 시간 (0-23) |
| send_minute | IntegerField | NULL, blank | 발송 분 (0-59) |

**관계:**
- template -> OneToOneField(CourseMessageTemplate, on_delete=CASCADE, related_name='schedule')

**Choices:**
- schedule_type: immediate=즉시 발송, same_day=당일 발송, next_day=다음날 발송

---

#### apply.apply_applicationformtemplate (ApplicationFormTemplate)

**파일**: `apply/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=100) | NOT NULL | |
| schema | JSONField | NOT NULL | |
| version | IntegerField | default=1 | |
| is_active | BooleanField | default=True | |
| description | TextField | NULL, blank | |
| course_semester_id | ForeignKey | NOT NULL, CASCADE | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

**관계:**
- course_semester -> ForeignKey(CourseSemester, on_delete=CASCADE)

**Meta:** unique_together = (course_semester, version)

---

### articles app

#### articles.articles_article (Article)

**파일**: `articles/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=120) | NOT NULL | |
| content | TextField | NOT NULL | |

**Meta:** ordering = [-id]

---

### attendance app

#### attendance.attendance_userattendance (UserAttendance)

**파일**: `attendance/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| status | CharField(max_length=1) | default='A' | choices: ATTENDANCE_STATUS |
| status_a_time | DateTimeField | auto_now_add | init |
| status_c_time | DateTimeField | NULL, blank | entrance |
| status_d_time | DateTimeField | NULL, blank | outing start |
| status_e_time | DateTimeField | NULL, blank | outing end |
| status_f_time | DateTimeField | NULL, blank | exit |
| status_g_time | DateTimeField | NULL, blank | system update |
| check_attendance_time | DurationField | default=timedelta(0) | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)

**Choices:**
- status: A=INIT, C=ENTRANCE, D=OUTING, E=ENTRANCE_W_OUTING, G=ABSENT, H=EARLY_DEPARTURE, I=ATTENDANCE

**Meta:** ordering = [status_a_time, user]; indexes = [status]

---

#### attendance.attendance_attendancealert (AttendanceAlert)

**파일**: `attendance/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| day_of_week | IntegerField | NOT NULL | choices: DAYS_OF_WEEK |
| alert_time | TimeField | NOT NULL | |
| is_active | BooleanField | default=True | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='attendance_alerts', on_delete=CASCADE)

**Choices:**
- day_of_week: 0=Monday ~ 6=Sunday

**Meta:** unique_together = (user, day_of_week, alert_time)

---

### auths app

#### auths.auth_sms (AuthSms)

**파일**: `auths/models.py`
**상속**: TimeStampedModel
**db_table**: `auth_sms`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| phone_number | CharField(max_length=13) | PK, regex: ^010-?\d{4}-?\d{4}$ | |
| auth_number | IntegerField | NOT NULL | 인증번호 |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

---

#### auths.auth_validcode (AuthValidcode)

**파일**: `auths/models.py`
**상속**: TimeStampedModel
**db_table**: `auth_validcode`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| valid_code | UUIDField | UNIQUE, default=uuid4, non-editable | |
| exp_date | DateTimeField | NOT NULL | |
| use | CharField(max_length=1) | NOT NULL | choices: USE_CHOICES |
| user_id | ForeignKey | NULL, blank, CASCADE | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)

**Choices:**
- use: T=token, I=invite

---

### blog app (Wagtail)

#### blog.BlogIndexPage (BlogIndexPage)

**파일**: `blog/models.py`
**상속**: wagtail.core.models.Page

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| (Page fields) | (inherited) | | Wagtail Page 기본 필드 |
| intro | RichTextField | blank | |

---

#### blog.BlogPage (BlogPage)

**파일**: `blog/models.py`
**상속**: wagtail.core.models.Page

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| (Page fields) | (inherited) | | Wagtail Page 기본 필드 |
| date | DateField | default=timezone.now | Post date |
| intro | CharField(max_length=250) | default='-' | |
| body | StreamField(BaseStreamBlock) | blank | Page body |
| document_id | ForeignKey | NULL, blank, SET_NULL | |

**관계:**
- document -> ForeignKey(wagtaildocs.Document, on_delete=SET_NULL, related_name='+')

---

### comcom app

#### comcom.comcom_cloudsettings (CloudSettings)

**파일**: `comcom/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | UUIDField (PK) | default=uuid4 | |
| key | CharField(max_length=255) | UNIQUE | Setting Key |
| value | JSONField | NOT NULL | Setting Value |
| description | TextField | blank | Description |
| last_updated | DateTimeField | auto_now | Last Updated |

---

#### comcom.comcom_cloudsettingslog (CloudSettingsLog)

**파일**: `comcom/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | UUIDField (PK) | default=uuid4 | |
| date | DateField | NOT NULL | Date |
| json_data | JSONField | NOT NULL | JSON Data |
| description | CharField(max_length=255) | NOT NULL | Description |

---

#### comcom.comcom_containerserver (ContainerServer)

**파일**: `comcom/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | UUIDField (PK) | default=uuid4 | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| server_host | CharField(max_length=255) | NOT NULL | Server Host |
| jupyter_url | URLField | blank | Jupyter URL |
| shell_url | URLField | blank | Shell URL |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- user -> ForeignKey(core.User, on_delete=CASCADE, related_name='container_servers')

**Meta:** unique_together = (user, server_host); ordering = [-created]

---

#### comcom.comcom_cloudapiroutinguser (CloudApiRoutingUser)

**파일**: `comcom/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | OneToOneField | NOT NULL, CASCADE | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- user -> OneToOneField(User, on_delete=CASCADE, related_name='cloud_api_routing')

---

### core app

#### core.core_user (User)

**파일**: `core/models.py`
**상속**: AbstractUser

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| email | EmailField | UNIQUE | |
| transformed_email | TextField | NULL, blank | |
| first_name | CharField(max_length=150) | blank | 이름 (성까지 포함) |
| username | CharField(max_length=150) | UNIQUE | Email 확인 |
| is_student | BooleanField | default=True | |
| is_coach | BooleanField | default=False | |
| is_editor | BooleanField | default=False | |
| is_cloud | BooleanField | default=False | |
| k_digital | BooleanField | default=False | |
| bio | TextField(max_length=500) | blank | |
| photo | ImageField | blank, upload_to='core/user/%Y/%m/%d' | |
| github | URLField | blank | |
| facebook | URLField | blank | |
| local_admin | BooleanField | default=False | |
| emp_no | CharField(max_length=20) | NULL, blank | |
| account_status | CharField(max_length=10) | default='active' | choices: ACCOUNT_STATUS_CHOICES |
| failed_login_attempts | PositiveIntegerField | default=0 | |
| (+ AbstractUser fields) | | | password, last_login, is_superuser, last_name, is_staff, is_active, date_joined |

**관계:**
- local_school <- ManyToManyField(core.LocalSchool, through='core.UserLocalSchool')

**Choices:**
- account_status: active=Active, inactive=Inactive, suspended=Suspended, deleted=Deleted

**Meta:** ordering = [first_name]

---

#### core.core_user_local_school (UserLocalSchool)

**파일**: `core/models.py`
**상속**: TimeStampedModel
**db_table**: `core_user_local_school`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| localschool_id | ForeignKey | NOT NULL, CASCADE | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

---

#### core.core_userstatus (UserStatus)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | OneToOneField | NOT NULL, CASCADE | |
| use_cloud | BooleanField | default=True | |
| reg_cloud | BooleanField | default=False | |
| pre_question1 | PositiveIntegerField | default=0 | choices: DEV_EXPERIENCE |
| pre_question2 | BooleanField | default=False | |

**관계:**
- user -> OneToOneField(User, on_delete=CASCADE)
- tags <- TaggableManager (django-taggit)

**Choices:**
- pre_question1: 0=없음, 1=초급, 2=중급, 3=고급

---

#### core.core_userprivacy (UserPrivacy)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | OneToOneField | NOT NULL, CASCADE | |
| unique_key | CharField(max_length=88) | NULL | |
| phone_number | CharField(max_length=13) | blank, regex | |
| birth | DateField | NULL, blank | |
| gender | CharField(max_length=1) | blank | choices: GENDER_CHOICES |
| address_type | CharField(max_length=1) | NULL | R(도로명), J(지번) |
| address1 | CharField(max_length=250) | NULL | 기본주소 |
| address2 | CharField(max_length=250) | NULL | 상세주소 |
| mkt_agreement_yn | BooleanField | default=True | |
| term_agreement_yn | BooleanField | default=False | |
| nb_card_yn | BooleanField | default=True | |
| mbti_id | ForeignKey | NULL, CASCADE | |
| persona_id | ForeignKey | NULL, CASCADE | |

**관계:**
- user -> OneToOneField(User, on_delete=CASCADE)
- mbti -> ForeignKey(core.Mbti, related_name='+', on_delete=CASCADE)
- persona -> ForeignKey(core.Persona, related_name='+', on_delete=CASCADE)

**Choices:**
- gender: M=남성, F=여성

---

#### core.core_mbti (Mbti)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| type | CharField(max_length=200) | NOT NULL | |
| description | TextField | blank | |

---

#### core.core_persona (Persona)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| group | CharField(max_length=3) | default='CUR' | choices: GROUP_CHOICES |
| description | TextField | blank | |
| color_light | ColorField | default='#FF0000' | |
| color_black | ColorField | default='#FF0000' | |

**Choices:**
- group: CUR=호기심, PAS=열정, WIN=상생, WIL=의지

---

#### core.core_student (Student)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | OneToOneField | NOT NULL, CASCADE | |

---

#### core.core_coach (Coach)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | OneToOneField | NOT NULL, CASCADE | |

---

#### core.core_editor (Editor)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | OneToOneField | NOT NULL, CASCADE | |

**Meta:** ordering = [user__first_name]

---

#### core.core_localschool (LocalSchool)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=100) | NOT NULL | |
| abstract | TextField | NOT NULL | |
| country | CountryField | default='KR' | |
| check_ip | BooleanField | default=True | |
| check_mac_addr | BooleanField | default=True | |
| city | CharField(max_length=30) | default='Asia/Seoul' | choices: tz_dictionary |
| public | BooleanField | default=False | |
| type | CharField(max_length=3) | default='CAM' | choices: TYPE_CHOICES |
| phone_number | CharField(max_length=13) | NULL, blank | |

**Choices:**
- type: CAM=캠퍼스, ONL=온라인, BIZ=기업교육, STA=내부

**Meta:** ordering = [id]

---

#### core.core_localschooltrustedips (LocalSchoolTrustedIps)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| local_school_id | ForeignKey | NOT NULL, CASCADE | |
| ip | GenericIPAddressField | NOT NULL | |

**Meta:** ordering = [local_school, ip]

---

#### core.core_roundschedule (RoundSchedule)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| start_date | DateTimeField | NOT NULL | |
| end_date | DateTimeField | NOT NULL | |
| round_number | PositiveIntegerField | default=1 | |
| is_available | BooleanField | default=True | |
| course_id | ForeignKey | default=72, CASCADE | |

**관계:**
- course -> ForeignKey(core.Course, related_name='+', on_delete=CASCADE)

**Meta:** ordering = [round_number, start_date]

---

#### core.core_category (Category)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| name | CharField(max_length=255) | NOT NULL | |
| description | TextField | NULL, blank | |
| image | ImageField | NULL, blank | upload_to='category/%Y/%m/%d' |
| order | PositiveIntegerField | default=1 | |

**Meta:** ordering = [order]

---

#### core.core_coursetype (CourseType -- core app)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| type | CharField(max_length=200) | db_index | |

---

#### core.core_course (Course)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| local_school_id | ForeignKey | NOT NULL, CASCADE | |
| order | SmallIntegerField | default=1, min=1 | |
| color | ColorField | default='#FF0000' | |
| course_type_id | ForeignKey | default=1, CASCADE | |
| title | CharField(max_length=200) | db_index | |
| seo_title | CharField(max_length=200) | blank | |
| slug | SlugField(max_length=200) | UNIQUE, db_index, allow_unicode | |
| image | ImageField | blank | upload_to='courses/%Y/%m/%d' |
| og_image | ImageField | blank | |
| abstract | TextField | blank | |
| meta_description | TextField | blank | |
| meta_keywords | TextField | blank | |
| price | DecimalField(max_digits=10, decimal_places=2) | NOT NULL | |
| stock | PositiveIntegerField | default=1 | |
| available_display | BooleanField | default=False | |
| available_order | BooleanField | default=False | |
| calendar_type | IntegerField | default=1 | |
| hrd_net_url_part1 | URLField | blank | |
| hrd_net_url_part2 | CharField(max_length=255) | blank | |
| lecture_type | CharField(max_length=30) | default='standard' | choices |
| is_cloud_used | BooleanField | default=False | 클라우드 사용 여부 |
| level | CharField(max_length=13) | db_index | choices |
| node_count | PositiveIntegerField | min=1 | 챕터수 |

**관계:**
- local_school -> ForeignKey(LocalSchool, related_name='+', on_delete=CASCADE)
- course_type -> ForeignKey(CourseType, related_name='+', on_delete=CASCADE)
- linked_courses <- ManyToManyField('self', symmetrical=False, related_name='linking_courses')

**Choices:**
- lecture_type: standard=STANDARD, vod=VOD
- level: BEGINNER=입문, ELEMENTARY=초급, INTERMEDIATE=중급, ADVANCED=고급

**Meta:** ordering = [order]; unique_together = (local_school, order); index_together = [id, slug]

---

#### core.core_onlinecourse (OnlineCourse)

**파일**: `core/models.py`
**상속**: Course (multi-table inheritance)

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| course_ptr_id | OneToOneField (PK) | CASCADE | Course 상속 |
| duration_type | CharField(max_length=10) | default='none' | choices: DURATION_CHOICES |
| duration_value | PositiveIntegerField | NULL, blank | 수강 기간 |
| cloud_usage_duration | PositiveIntegerField | NULL, blank, min=1 | 클라우드 사용 기간 (일) |
| summary | TextField | NOT NULL | 서머리 |
| discount_rate | DecimalField(5,2) | NULL, blank | 할인율 |
| selling_price | DecimalField(10,2) | NOT NULL | 판매가 |
| is_government_funded | BooleanField | NOT NULL | 국비지원여부 |
| is_subject | BooleanField | default=False | 패키지여부 |
| learning_tool | CharField(max_length=50) | NULL, blank | 학습툴/프로그램 |
| digital_friendly | PositiveIntegerField | min=1 | |
| contents | TextField | NOT NULL | |
| view_count | PositiveIntegerField | default=0 | |

**관계:**
- categories <- ManyToManyField(Category, related_name='category_courses')
- label <- TaggableManager (through=LabelTaggedItem)
- bookmarks <- ManyToManyField(AUTH_USER_MODEL, through='core.Bookmark')

**Choices:**
- duration_type: none=No Limit, fixed=Fixed Schedule, dynamic=From Purchase Date

---

#### core.core_labelttaggeditem (LabelTaggedItem)

**파일**: `core/models.py`
**상속**: TaggedItemBase

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| content_object_id | ForeignKey | NOT NULL, CASCADE | -> OnlineCourse |
| tag_id | ForeignKey | (inherited) | -> taggit.Tag |

---

#### core.core_skilltaggeditem (SkillTaggedItem)

**파일**: `core/models.py`
**상속**: TaggedItemBase

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| content_object_id | ForeignKey | NOT NULL, CASCADE | -> OnlineCourse |
| tag_id | ForeignKey | (inherited) | -> taggit.Tag |

---

#### core.core_courseprogrs (CourseProgrs)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_enrolments_id | ForeignKey | default=1, PROTECT | |
| status | CharField(max_length=1) | default='Z' | |
| status_z_time | DateTimeField | auto_now_add | not approved |
| status_a_time | DateTimeField | NULL, blank | before proceeding |
| status_b_time | DateTimeField | NULL, blank | possible to proceed |
| status_c_time | DateTimeField | NULL, blank | proceeding |
| status_d_time | DateTimeField | NULL, blank | admin deny |
| status_f_time | DateTimeField | NULL, blank | refund |
| status_g_time | DateTimeField | NULL, blank | finish |
| status_h_time | DateTimeField | NULL, blank | complete |
| status_i_time | DateTimeField | NULL, blank | delay |
| status_j_time | DateTimeField | NULL, blank | serious delay |

**관계:**
- user_enrolments -> ForeignKey(core.UserEnrolments, related_name='course_progrs', on_delete=PROTECT)

**Meta:** ordering = [user_enrolments__subject]

---

#### core.core_submissionmethod (SubmissionMethod)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| method | CharField(max_length=4) | UNIQUE | choices: METHOD_CHOICES |

**Choices:**
- method: Quiz, Code, Proj, Kcod, Vime, Kico, File, None

---

#### core.core_enrol (Enrol)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| enrol_start_date | DateTimeField | NOT NULL | |
| enrol_end_date | DateTimeField | NOT NULL | |
| is_schedule | BooleanField | default=True | |
| description | TextField | NOT NULL | |
| service_type | CharField(max_length=1) | default='A' | choices: SERVICE_CHOICES |
| lunch_start_time | TimeField | default=13:00 | |
| lunch_end_time | TimeField | default=14:00 | |
| training_id | CharField(max_length=20) | default='AIG202000000000' | |
| training_round_number | IntegerField | default=1 | |
| require_attendance | BooleanField | default=False | |
| require_authenticate | BooleanField | default=False | |
| admit_attendance_time | DurationField | default=7h30m | |
| extend_attendance_time | DurationField | default=10m | |
| hrd_information_id | ForeignKey | NULL, blank, CASCADE | |
| training_time | DurationField | NULL, blank | |

**관계:**
- course -> ForeignKey(Course, related_name='+', on_delete=CASCADE)
- hrd_information -> ForeignKey(core.HrdInformation, on_delete=CASCADE)
- submission_methods <- ManyToManyField(SubmissionMethod, blank=True)

**Choices:**
- service_type: A=KDT, B=KDC, C=B2B, D=B2C, E=BDT

**Meta:** ordering = [id]; constraints: start_before_end_enrol

---

#### core.core_userenrolments (UserEnrolments)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| enrol_id | ForeignKey | NOT NULL, CASCADE | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| start_time | DateTimeField | NULL, blank | |
| end_time | DateTimeField | NULL, blank | |
| retake_status | IntegerField | default=0 | |
| subject_id | ForeignKey | NULL, blank, CASCADE | |
| status | CharField(max_length=20) | default='ACTIVE' | choices |

**관계:**
- enrol -> ForeignKey(Enrol, related_name='+', on_delete=CASCADE)
- user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)
- subject -> ForeignKey(core.Subject, related_name='+', on_delete=CASCADE)

**Choices:**
- status: ACTIVE=active, INACTIVE=inactive

**Meta:** unique_together = (enrol, user, retake_status); constraints: start_before_end_userenrolments

---

#### core.core_dockerimage (DockerImage)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| cluster_type | CharField(max_length=4) | default='cpu' | choices |
| repositories | TextField | default='moduaiffel/cloud_test' | |
| tag | CharField(max_length=200) | NOT NULL | |

**Choices:**
- cluster_type: cpu=cpu, gpu=gpu

**Meta:** ordering = [id]

---

#### core.core_node (Node)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=100) | NOT NULL, regex validator | |
| abstract | TextField | NOT NULL | |
| is_lecture | BooleanField | default=True | |
| is_project | BooleanField | default=False | |
| is_tutorial | BooleanField | default=False | |
| is_aico | BooleanField | default=False | |
| difficulty | CharField(max_length=20) | NULL, blank | choices: DIFFICULTY_CHOICES |

**Choices:**
- difficulty: BEGINNER=매우 쉬움, ELEMENTARY=쉬움, INTERMEDIATE=보통, ADVANCED=어려움, PROFICIENT=매우 어려움

**Meta:** ordering = [title]

---

#### core.core_nodeversion (NodeVersion)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_id | ForeignKey | NOT NULL, CASCADE | |
| version | PositiveSmallIntegerField | default=1 | |
| author_id | ForeignKey | NOT NULL, CASCADE | |
| created_on | DateTimeField | auto_now_add | |
| use_gpu | BooleanField | default=False | |
| use_openai_api_key | BooleanField | default=False | |
| storage_path | CharField(max_length=255) | NULL, blank | |
| docker_image_id | ForeignKey | NULL, blank, CASCADE | |
| resource_slug | CharField(max_length=50) | NULL, blank | |
| metadata | JSONField | default=dict | |

**관계:**
- node -> ForeignKey(Node, related_name='+', on_delete=CASCADE)
- author -> ForeignKey(core.Editor, related_name='+', on_delete=CASCADE)
- docker_image -> ForeignKey(DockerImage, related_name='+', on_delete=CASCADE)

**Meta:** ordering = [node__title]; unique_together = (node, version)

---

#### core.core_nodeschedule (NodeSchedule)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| enrol_id | ForeignKey | NOT NULL, CASCADE | |
| node_id | ForeignKey | NULL, CASCADE | |
| node_version_id | ForeignKey | default=1, CASCADE | |
| start_time | DateTimeField | NULL, blank | |
| end_time | DateTimeField | NULL, blank | |
| estimate_time | DurationField | default=1day | |

**관계:**
- enrol -> ForeignKey(Enrol, related_name='+', on_delete=CASCADE)
- node -> ForeignKey(Node, related_name='+', on_delete=CASCADE)
- node_version -> ForeignKey(NodeVersion, related_name='node_schedule', on_delete=CASCADE)

**Meta:** ordering = [enrol, start_time]; constraints: start_before_end_nodeschedule

---

#### core.core_nodeprogrs (NodeProgrs)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_enrolments_id | ForeignKey | NOT NULL, CASCADE | |
| node_schedule_id | ForeignKey | NULL, CASCADE | |
| status | CharField(max_length=1) | default='A' | |
| coach_id | ForeignKey | NOT NULL, CASCADE | |
| comment | TextField | NULL, blank | |
| status_a_time | DateTimeField | auto_now_add | before proceeding |
| status_b_time | DateTimeField | NULL, blank | today_todo |
| status_c_time | DateTimeField | NULL, blank | proceeding |
| status_d_time | DateTimeField | NULL, blank | proceeding complete |
| status_e_time | DateTimeField | NULL, blank | evaluation |
| status_f_time | DateTimeField | NULL, blank | evaluation complete |
| status_g_time | DateTimeField | NULL, blank | finish |
| status_h_time | DateTimeField | NULL, blank | delay |

**관계:**
- user_enrolments -> ForeignKey(UserEnrolments, related_name='nodeprogrs', on_delete=CASCADE)
- node_schedule -> ForeignKey(NodeSchedule, related_name='+', on_delete=CASCADE)
- coach -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)

**Meta:** ordering = [user_enrolments, node_schedule]; indexes = [status]; unique_together = (user_enrolments, node_schedule)

**Proxy:** NodeProgrsSummary (proxy=True)

---

#### core.core_coursenodeversionrelation (CourseNodeVersionRelation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_version_id | ForeignKey | NOT NULL, CASCADE | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| order | PositiveSmallIntegerField | default=1 | |

**관계:**
- node_version -> ForeignKey(NodeVersion, related_name='+', on_delete=CASCADE)
- course -> ForeignKey(Course, related_name='+', on_delete=CASCADE)

**Meta:** ordering = [course, order]; unique_together = (node_version, course)

---

#### core.core_step (Step)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_version_id | ForeignKey | NOT NULL, CASCADE | |
| order | PositiveSmallIntegerField | default=1, min=1 | |
| title | CharField(max_length=100) | NOT NULL | |
| is_code | BooleanField | default=True | |
| url | CharField(max_length=255) | NOT NULL, default='t-1-1' | |
| estimate_time | DurationField | default=1h | |
| has_video | BooleanField | default=False | |
| has_quiz | BooleanField | default=False | |
| content | JSONField | NULL, blank | |

**관계:**
- node_version -> ForeignKey(NodeVersion, related_name='steps', on_delete=CASCADE)

**Meta:** ordering = [order]

---

#### core.core_stepcompt (StepCompt)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| node_version_id | ForeignKey | default=1, CASCADE | |
| step_id | ForeignKey | default=1, CASCADE | |
| status | CharField(max_length=1) | default='a' | |
| start_time | DateTimeField | auto_now_add | |
| end_time | DateTimeField | auto_now | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)
- node_version -> ForeignKey(NodeVersion, related_name='+', on_delete=CASCADE)
- step -> ForeignKey(Step, related_name='step_compt', on_delete=CASCADE)

**Meta:** ordering = [user, node_version, step]; unique_together = (user, node_version, step)

**Proxy:** StepComptSummary (proxy=True)

---

#### core.core_rubric (Rubric)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_id | ForeignKey | NOT NULL, CASCADE | |
| order | SmallIntegerField | default=1, min=1 | |
| metric | TextField | NULL, blank | |

**관계:**
- node -> ForeignKey(Node, related_name='rubric', on_delete=CASCADE)
- tags <- TaggableManager (django-taggit)

**Meta:** ordering = [node, order]

---

#### core.core_rubriccategory (RubricCategory)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| rubric_id | ForeignKey | NOT NULL, CASCADE | |
| order | SmallIntegerField | default=1, min=1 | |
| score | IntegerField | default=1 | |
| eval_standard | TextField | NULL, blank | |

**관계:**
- rubric -> ForeignKey(Rubric, related_name='rubric_category', on_delete=CASCADE)

**Meta:** ordering = [rubric, order]

---

#### core.core_evaluation (Evaluation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_progrs_id | ForeignKey | default=1, CASCADE | |
| rubric_id | ForeignKey | NOT NULL, CASCADE | |
| score | SmallIntegerField | default=0 | |

**관계:**
- node_progrs -> ForeignKey(NodeProgrs, related_name='evaluation', on_delete=CASCADE)
- rubric -> ForeignKey(Rubric, related_name='+', on_delete=CASCADE)

**Meta:** ordering = [rubric]; unique_together = (node_progrs, rubric)

**Proxy:** EvaluationSummary (proxy=True)

---

#### core.core_survey (Survey -- core app)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_version_id | ForeignKey | NOT NULL, CASCADE | |
| intro | TextField | NOT NULL | |
| questions | TextField | NOT NULL | |

**관계:**
- node_version -> ForeignKey(NodeVersion, related_name='+', on_delete=CASCADE)

---

#### core.core_surveyanswer (SurveyAnswer)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| survey_id | ForeignKey | NOT NULL, CASCADE | |
| answerd_on | DateTimeField | auto_now_add | |
| answer | TextField | NOT NULL | |
| answer2 | TextField | NOT NULL | |

---

#### core.core_usersubmission (UserSubmission)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| node_id | ForeignKey | NOT NULL, CASCADE | |
| node_version_id | ForeignKey | default=1, CASCADE | |
| page_slug | CharField(max_length=255) | blank | |
| submit_type | CharField(max_length=4) | default='Quiz' | choices: METHOD_CHOICES |
| submit_data | TextField | NULL, blank | |
| submit_block_id | CharField(max_length=36) | NOT NULL | |
| submit_time | DateTimeField | auto_now_add | |
| block_order | IntegerField | default=0 | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)
- node -> ForeignKey(Node, related_name='user_submission', on_delete=CASCADE)
- node_version -> ForeignKey(NodeVersion, related_name='+', on_delete=CASCADE)

**Meta:** ordering = [-submit_time]

---

#### core.core_usersubmissionmetadata (UserSubmissionMetadata)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_submission_id | OneToOneField | NOT NULL, CASCADE | |
| url | TextField | NOT NULL | |
| url_type | CharField(max_length=16) | default='unknown' | choices |
| data | JSONField | default=dict, blank | |
| status | CharField(max_length=16) | default='pending' | choices |
| last_synced_at | DateTimeField | NULL, blank | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

**관계:**
- user_submission -> OneToOneField(UserSubmission, related_name='metadata', on_delete=CASCADE)

**Choices:**
- url_type: youtube, notion, generic, unknown
- status: pending, success, failed

**Meta:** ordering = [-updated_at]

---

#### core.core_userchallenge (UserChallenge)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| title | CharField(max_length=50) | NOT NULL | |
| abstract | CharField(max_length=70) | NOT NULL | |
| start_time | DateField | NOT NULL | |
| end_time | DateField | NOT NULL | |
| proj_url | URLField | blank | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='my_challenge_set', on_delete=CASCADE)

**Meta:** ordering = [user__id]; constraints: start_before_end_userchallenge

---

#### core.core_usermacaddr (UserMacAddr)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| browser | CharField(max_length=50) | NOT NULL | |
| visitor_id | CharField(max_length=20) | NOT NULL | |
| logged_time | DateTimeField | auto_now_add | |

**Meta:** ordering = [user__id, browser]

---

#### core.core_userlogentry (UserLogEntry)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| action | CharField(max_length=64) | NOT NULL | |
| datetime | DateTimeField | auto_now_add | |
| ip | GenericIPAddressField | NULL | |
| user_agent | CharField(max_length=300) | NOT NULL | |
| user_enrolments_id | ForeignKey | NULL, blank, CASCADE | |
| authentication_yn | BooleanField | default=False, NULL, blank | |
| auth_code | CharField(max_length=64) | NULL, blank | |

**Meta:** ordering = [-datetime]

---

#### core.core_cloudcontainerentry (CloudContainerEntry)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| node_schedule_id | ForeignKey | NULL, CASCADE | |
| created_time | DateTimeField | auto_now_add | |

**Meta:** ordering = [-created_time]

---

#### core.core_subject (Subject)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=50) | NOT NULL | |
| service_type | CharField(max_length=50) | NULL, blank | |
| created_at | DateTimeField | auto_now_add | |

**Meta:** ordering = [title]

---

#### core.core_subjectprogrs (SubjectProgrs)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| status | CharField(max_length=50) | NOT NULL | |
| status_a_time | DateTimeField | auto_now_add | before proceeding |
| status_b_time | DateTimeField | NULL, blank | proceeding |
| status_c_time | DateTimeField | NULL, blank | finish |

---

#### core.core_subjectcourserelation (SubjectCourseRelation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| subject_id | ForeignKey | NOT NULL, CASCADE | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| order | PositiveSmallIntegerField | default=1 | |

**Meta:** ordering = [subject, order]; unique_together = (subject, course)

---

#### core.core_subjectsummary (SubjectSummary)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| subject_id | ForeignKey | NOT NULL, CASCADE | |
| avg_prog_pct | PositiveIntegerField | NOT NULL | |
| avg_comp_pct | PositiveIntegerField | NOT NULL | |
| avg_eval_score | FloatField | NULL, blank | |
| acc_enrol_cnt | PositiveIntegerField | NULL, blank | |

**Meta:** ordering = [subject]

---

#### core.core_userboardsummary (UserboardSummary)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| subject_id | ForeignKey | NOT NULL, CASCADE | |
| tot_comp_pct | PositiveIntegerField | NOT NULL | |
| user_activity_score | PositiveIntegerField | NOT NULL | |

---

#### core.core_waitinglist (WaitingList)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| fullname | CharField(max_length=50) | NOT NULL | |
| email | EmailField(max_length=254) | NOT NULL | |
| is_student | BooleanField | default=True | |
| is_coach | BooleanField | default=False | |
| local_school_id | ForeignKey | NOT NULL, CASCADE | |
| emp_no | CharField(max_length=50) | blank | |
| enrol_id | ForeignKey | NULL, blank, CASCADE | |
| user_id | ForeignKey | NULL, CASCADE | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |
| has_invited | BooleanField | default=False | |
| subject_id | ForeignKey | NULL, blank, CASCADE | |
| round_schedule_id | ForeignKey | NULL, blank, CASCADE | |

**관계:**
- local_school -> ForeignKey(LocalSchool, related_name='+', on_delete=CASCADE)
- enrol -> ForeignKey(Enrol, related_name='+', on_delete=CASCADE)
- user -> ForeignKey(AUTH_USER_MODEL, on_delete=CASCADE)
- subject -> ForeignKey(Subject, on_delete=CASCADE)
- round_schedule -> ForeignKey(RoundSchedule, on_delete=CASCADE)

---

#### core.core_waitinglistauthvalidcoderelation (WaitinglistAuthvalidcodeRelation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| waiting_list_id | ForeignKey | NOT NULL, CASCADE | |
| auth_validcode_id | ForeignKey | NOT NULL, CASCADE | |

**Meta:** unique_together = (waiting_list, auth_validcode)

---

#### core.core_usercreditevent (UserCreditEvent)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NULL, PROTECT | |
| local_school_id | ForeignKey | NULL, PROTECT | |
| action | PositiveSmallIntegerField | NOT NULL | choices: ACTION_TYPE_CHOICES |
| amount | SmallIntegerField | default=0 | |
| transaction_key_id | ForeignKey | NULL, CASCADE | |
| transaction_description | CharField(max_length=100) | NOT NULL | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='credit_event', on_delete=PROTECT)
- local_school -> ForeignKey(LocalSchool, related_name='credit_event', on_delete=PROTECT)
- transaction_key -> ForeignKey(NodeVersion, related_name='credit_event', on_delete=CASCADE)

**Meta:** ordering = [-created]

---

#### core.core_usercreditdetail (UserCreditDetail)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| action | PositiveSmallIntegerField | NOT NULL | choices: ACTION_TYPE_CHOICES |
| transaction_point | SmallIntegerField | NOT NULL | |
| detail_cancle_id | ForeignKey | NOT NULL, CASCADE | self |
| dateil_accumulate_id | ForeignKey | NOT NULL, CASCADE | self |
| history_event_id | ForeignKey | NOT NULL, CASCADE | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='credit_detail', on_delete=CASCADE)
- detail_cancle -> ForeignKey('self', related_name='cancle', on_delete=CASCADE)
- dateil_accumulate -> ForeignKey('self', related_name='accumulate', on_delete=CASCADE)
- history_event -> ForeignKey(UserCreditEvent, related_name='credit_detail', on_delete=CASCADE)

**Meta:** ordering = [-created]

---

#### core.core_termsandconditions (TermsAndConditions)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| term_type | CharField(max_length=40) | NOT NULL | choices: TERM_TYPES |
| term_version | IntegerField | NOT NULL | |
| term_path | CharField(max_length=255) | NOT NULL | |
| service | CharField(max_length=20) | NOT NULL | choices: SERVICES |
| retention_period_years | IntegerField | NOT NULL | |
| effective_date | DateField | NOT NULL | |

**Choices:**
- term_type: TermsOfUse, PrivacyPolicy, MarketingConsent, RefundPolicy
- service: APPLY, CAMPUS, KDC, ONLINE

---

#### core.core_useractionhistory (UserActionHistory)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NULL, blank, CASCADE | |
| application_form_id | ForeignKey | NULL, blank, CASCADE | |
| term_id | ForeignKey | NOT NULL, CASCADE | |
| action | CharField(max_length=10) | NOT NULL | choices: ACTIONS |
| action_date | DateTimeField | NOT NULL | |
| next_notification_date | DateTimeField | NOT NULL | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, on_delete=CASCADE)
- application_form -> ForeignKey(apply.ApplicationForm, on_delete=CASCADE)
- term -> ForeignKey(core.TermsAndConditions, on_delete=CASCADE)

**Choices:**
- action: Agreed, Disagreed

---

#### core.core_hrdinformation (HrdInformation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| training_id | CharField(max_length=255) | default='AIG20200000313409' | |
| round_number | PositiveIntegerField | default=1 | |
| training_type | CharField(max_length=255) | default='K-디지털 트레이닝' | |
| company | CharField(max_length=255) | default='(주)모두의연구소' | |
| title | CharField(max_length=255) | NOT NULL | |
| applicants | IntegerField | default=0 | |
| capacity | IntegerField | default=0 | |
| tuition | DecimalField(10,2) | NOT NULL | |
| training_start_date | DateField | db_index | |
| training_end_date | DateField | db_index | |

**Meta:** ordering = [training_id, round_number]; unique_together = (training_id, round_number)

---

#### core.core_file (File)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_file_name | CharField(max_length=255) | NOT NULL | |
| path | CharField(max_length=255) | NOT NULL | |
| size | BigIntegerField | NOT NULL | |
| is_deleted | BooleanField | default=False | |
| uploaded_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

---

#### core.core_bookmark (Bookmark)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| course_id | ForeignKey | NOT NULL, CASCADE | -> OnlineCourse |
| created_at | DateTimeField | auto_now_add | |
| is_active | BooleanField | default=True | |

---

#### core.core_acquiredskill (AcquiredSkill)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| skill_name | CharField(max_length=100) | NOT NULL | |
| skill_logo | ImageField | blank | upload_to='core/skills/original_images' |

**관계:**
- courses <- ManyToManyField(OnlineCourse, related_name='acquired_skills')

---

#### core.core_useracquiredskill (UserAcquiredSkill)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| skill_id | ForeignKey | NOT NULL, CASCADE | |
| acquired_date | DateTimeField | NOT NULL | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='user_skills', on_delete=CASCADE)
- skill -> ForeignKey(AcquiredSkill, related_name='users_acquired', on_delete=CASCADE)

---

#### core.core_cloudaccessperiod (CloudAccessPeriod)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| start_date | DateTimeField | NOT NULL | |
| end_date | DateTimeField | NOT NULL | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='cloud_usages', on_delete=CASCADE)
- course -> ForeignKey(Course, related_name='cloud_usages', on_delete=CASCADE)

---

#### core.core_openaiapikeys (OpenaiAPiKeys)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| name | CharField(max_length=100) | NOT NULL | |
| key | CharField(max_length=255) | NOT NULL | |
| status | CharField(max_length=10) | default='active' | choices: ACCOUNT_STATUS_CHOICES |

---

#### core.core_userapikeyassignment (UserApiKeyAssignment)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| api_key_id | ForeignKey | NOT NULL, CASCADE | |
| assigned_date | DateTimeField | auto_now_add | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='user_assignments', on_delete=CASCADE)
- api_key -> ForeignKey(OpenaiAPiKeys, related_name='api_key_assignments', on_delete=CASCADE)

---

#### core.core_rubricgptevaluation (RubricGptEvaluation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| evaluation_id | OneToOneField | NOT NULL, CASCADE | |
| gpt_score | SmallIntegerField | default=0 | |
| gpt_comment | TextField | NULL, blank | |

**관계:**
- evaluation -> OneToOneField(Evaluation, related_name='rubric_gpt_evaluations', on_delete=CASCADE)

---

#### core.core_gptevaluation (GptEvaluation)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_progrs_id | ForeignKey | NOT NULL, CASCADE | |
| overall_comment | TextField | NULL, blank | |
| api_type | CharField(max_length=50) | default='chat_completions' | choices |

**관계:**
- node_progrs -> ForeignKey(NodeProgrs, related_name='gpt_evaluation', on_delete=CASCADE)

**Choices:**
- api_type: chat_completions=Chat Completions API, responses=Responses API (with web_search)

**Meta:** indexes = [api_type]

---

#### core.core_summaryevaluationdata (SummaryEvaluationData)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_id | ForeignKey | NOT NULL, CASCADE | |
| total_evaluations | IntegerField | default=0 | 총 평가 건수 |
| average_score | DecimalField(3,2) | NULL, blank | 평균 점수 |
| common_feedback | TextField | NULL, blank | 가장 일반적인 피드백 |
| key_points | TextField | NULL, blank | 주요 평가 포인트 |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- node -> ForeignKey(Node, related_name='summary_evaluation', on_delete=CASCADE)

**Meta:** unique_together = [node, created]

---

#### core.core_video (Video)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=100) | NOT NULL | |
| version | SmallIntegerField | NOT NULL | |
| width | SmallIntegerField | NOT NULL | |
| height | SmallIntegerField | NOT NULL | |
| bucket_path | CharField(max_length=300) | NULL, blank | |
| hls_file | CharField(max_length=300) | NOT NULL | |
| thumbnail_file | CharField(max_length=300) | NOT NULL | |
| origin_file | CharField(max_length=300) | NOT NULL | |
| file_size | BigIntegerField | default=0 | |
| duration | DurationField | default=0 | |
| user_file | CharField(max_length=300) | NOT NULL | |
| is_deleted | BooleanField | default=False | |

---

#### core.core_stepvideo (StepVideo)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| step_id | ForeignKey | NOT NULL, CASCADE | |
| video_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_uservideoprogress (UserVideoProgress)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| step_compt_id | ForeignKey | NOT NULL, CASCADE | |
| video_id | ForeignKey | NOT NULL, CASCADE | |
| progress_seconds | PositiveIntegerField | default=0, NULL, blank | |
| completed | BooleanField | default=False | |

---

#### core.core_learningmaterial (LearningMaterial)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=255) | NOT NULL | |
| material_type | CharField(max_length=10) | NOT NULL | choices |
| content | TextField | NOT NULL | url or file_path |
| data_size | BigIntegerField | default=0 | |

**Choices:**
- material_type: url=URL, file=FILE

---

#### core.core_courselearningmaterial (CourseLearningMaterial)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| learning_material_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_steplearningmaterial (StepLearningMaterial)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| step_id | ForeignKey | NOT NULL, CASCADE | |
| learning_material_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_quiz (Quiz)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| question | CharField(max_length=255) | NOT NULL | |
| question_type | CharField(max_length=30) | NOT NULL | choices |
| options | JSONField | NULL, blank | |
| correct_option | JSONField | NULL, blank | |
| hint | TextField | NULL, blank | |
| correct_guide | TextField | NULL, blank | |
| incorrect_guide | TextField | NULL, blank | |
| order | PositiveSmallIntegerField | default=1 | |

**Choices:**
- question_type: multiple_choice=Multiple Choice, subjective=Subjective

---

#### core.core_evaluationquestion (EvaluationQuestion)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| question | CharField(max_length=255) | NOT NULL | |
| options | JSONField | NULL, blank | |
| correct_option | JSONField | NULL, blank | |
| explanation | TextField | NULL, blank | |
| order | PositiveSmallIntegerField | default=1 | |

---

#### core.core_stepquiz (StepQuiz)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| step_id | ForeignKey | NOT NULL, CASCADE | |
| quiz_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_nodeversionquestion (NodeVersionQuestion)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_version_id | ForeignKey | NOT NULL, CASCADE | |
| evaluation_questions_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_quizsubmission (QuizSubmission)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| quiz_id | ForeignKey | NOT NULL, CASCADE | |
| step_compt_id | ForeignKey | NOT NULL, CASCADE | |
| submitted_at | DateTimeField | auto_now_add | |
| answer | TextField | NOT NULL | |

**Meta:** unique_together = [user, quiz, step_compt]

---

#### core.core_evaluationsubmission (EvaluationSubmission)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| evaluation_questions_id | ForeignKey | NOT NULL, CASCADE | |
| node_progrs_id | ForeignKey | NOT NULL, CASCADE | |
| submitted_at | DateTimeField | auto_now_add | |
| answers | TextField | NOT NULL | |

---

#### core.core_userfeedback (UserFeedback)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_enrolments_id | ForeignKey | NULL, SET_NULL | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| score | DecimalField(3,1) | NOT NULL | |
| content | TextField | NOT NULL | |

---

#### core.core_note (Note)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| step_compt_id | ForeignKey | NOT NULL, CASCADE | |
| timestamp_seconds | PositiveIntegerField | NOT NULL | |
| content | TextField(max_length=1000) | blank | |
| is_deleted | BooleanField | default=False | |

**Meta:** ordering = [created]

---

#### core.core_mainsection (MainSection)

**파일**: `core/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| title | CharField(max_length=255) | NOT NULL | Section Title |
| subtitle | CharField(max_length=255) | NOT NULL | Section Subtitle |
| order | PositiveIntegerField | NOT NULL | Section Order |
| course_ids | JSONField | NOT NULL | Included Item IDs |

**Meta:** ordering = [order]

---

#### core.core_usersubmissionfile (UserSubmissionFile)

**파일**: `core/models.py`
**상속**: FileRelation (abstract)

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| file_id | ForeignKey | NOT NULL, CASCADE | |
| created_at | DateTimeField | auto_now_add | |
| user_submission_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_learningmaterialfile (LearningMaterialFile)

**파일**: `core/models.py`
**상속**: FileRelation (abstract)

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| file_id | ForeignKey | NOT NULL, CASCADE | |
| created_at | DateTimeField | auto_now_add | |
| learning_material_id | ForeignKey | NOT NULL, CASCADE | |

---

#### core.core_stepcomptqueue (StepComptQueue)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| step_compt_id | ForeignKey | NOT NULL, CASCADE | |
| course_id | ForeignKey | NOT NULL, CASCADE | |
| priority | IntegerField | default=1 | 숫자가 높을수록 우선순위가 높음 |
| is_completed | BooleanField | default=False | |
| resolved_at | DateTimeField | NULL, blank | |
| resolved_by_id | ForeignKey | NULL, blank, CASCADE | |
| local_school_id | ForeignKey | NULL, blank, CASCADE | |

**Meta:** ordering = [-created, -priority]

---

#### core.core_user_instance_access_log (UserInstanceAccessLog)

**파일**: `core/models.py`
**db_table**: `core_user_instance_access_log`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| user_id | OneToOneField (PK) | CASCADE | |
| last_access_time | DateTimeField | NULL, blank | |
| created_at | DateTimeField | auto_now_add | |
| modified_at | DateTimeField | auto_now | |

**관계:**
- user -> OneToOneField(AUTH_USER_MODEL, primary_key=True, related_name='instance_access_log', on_delete=CASCADE)

---

#### core.core_notebookfile (NotebookFile)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| file | FileField | NOT NULL | upload_to='notebooks/%Y/%m/%d/' |
| title | CharField(max_length=255) | NOT NULL | |
| description | TextField | NULL, blank | |
| file_size | BigIntegerField | NULL, blank | |
| file_name | CharField(max_length=255) | NULL, blank | |
| mime_type | CharField(max_length=100) | NULL, blank | |
| is_deleted | BooleanField | default=False | |

---

#### core.core_nodenotebookrelation (NodeNotebookRelation)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_id | ForeignKey | NOT NULL, CASCADE | |
| notebook_id | ForeignKey | NOT NULL, CASCADE | |

**관계:**
- node -> ForeignKey(Node, related_name='notebook_relations', on_delete=CASCADE)
- notebook -> ForeignKey(NotebookFile, related_name='node_relations', on_delete=CASCADE)

---

#### core.core_nodeversionnotebookrelation (NodeVersionNotebookRelation)

**파일**: `core/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| node_version_id | ForeignKey | NOT NULL, CASCADE | |
| notebook_id | ForeignKey | NOT NULL, CASCADE | |

**관계:**
- node_version -> ForeignKey(NodeVersion, related_name='notebook_relations', on_delete=CASCADE)
- notebook -> ForeignKey(NotebookFile, related_name='node_version_relations', on_delete=CASCADE)

---

### core.survey app

#### core.survey.survey_answer (Answer)

**파일**: `core/survey/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| question_id | ForeignKey | NOT NULL, CASCADE | -> survey.Question (3rd party) |
| response_id | ForeignKey | NOT NULL, CASCADE | -> survey.Response (3rd party) |
| created | DateTimeField | auto_now_add | |
| updated | DateTimeField | auto_now | |
| body | TextField | NULL, blank | Content |
| unit | CharField(max_length=10) | NOT NULL | |
| node_version_id | ForeignKey | NULL, blank, CASCADE | |

**관계:**
- question -> ForeignKey(survey.Question, related_name='+', on_delete=CASCADE)
- response -> ForeignKey(survey.Response, related_name='+', on_delete=CASCADE)
- node_version -> ForeignKey(core.NodeVersion, related_name='+', on_delete=CASCADE)

**Proxy:** AnswerSummary (proxy=True)

---

#### core.survey.survey_coursesurvey (CourseSurvey)

**파일**: `core/survey/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| course_id | ForeignKey | NOT NULL, CASCADE | -> core.Course |
| survey_id | ForeignKey | NOT NULL, CASCADE | -> survey.Survey (3rd party) |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

---

#### core.survey.survey_coursecorrectanswer (CourseCorrectAnswer)

**파일**: `core/survey/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| question_id | ForeignKey | NOT NULL, CASCADE | -> survey.Question |
| correct_answer | TextField | NOT NULL | Content |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

---

#### core.survey.survey_pretestscore (PreTestScore)

**파일**: `core/survey/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_enrolments_id | ForeignKey | NOT NULL, CASCADE | |
| survey_id | ForeignKey | NOT NULL, CASCADE | -> survey.Survey (3rd party) |
| score | CharField(max_length=3) | NOT NULL | |
| level | CharField(max_length=40) | NOT NULL | |

---

### coupon app

#### coupon.coupon_coupon (Coupon)

**파일**: `coupon/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| code | CharField(max_length=50) | UNIQUE | |
| use_from | DateTimeField | NOT NULL | |
| use_to | DateTimeField | NOT NULL | |
| amount | IntegerField | min=0, max=300000 | |
| active | BooleanField | NOT NULL | |

---

### forum app

#### forum.forum_tags (Tags)

**파일**: `forum/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| name | CharField(max_length=50) | UNIQUE | |

---

#### forum.forum_category (Category)

**파일**: `forum/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| name | CharField(max_length=255) | NOT NULL | |
| color | ColorField | default='#0088CC' | |
| created_at | DateTimeField | auto_now_add | |
| updated_at | DateTimeField | auto_now | |

---

#### forum.forum_attachment (Attachment)

**파일**: `forum/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| uploader_id | ForeignKey | NULL, blank, SET_NULL | |
| uploader_name | CharField(max_length=255) | NOT NULL | |
| filename | CharField(max_length=255) | db_index | |
| size | PositiveIntegerField | default=0, db_index | |
| file | FileField(max_length=255) | NULL, blank | upload_to='notice/upload/...' |

---

#### forum.forum_topic (Topic)

**파일**: `forum/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| board_type | CharField(max_length=10) | default='archive', db_index | choices: BOARD_TYPE_CHOICES |
| topicker_id | ForeignKey | NULL, SET_NULL | |
| title | CharField(max_length=255) | NOT NULL | |
| slug | CharField(max_length=255) | NOT NULL | |
| first_post_id | ForeignKey | NULL, blank, SET_NULL | |
| course_type_id | ForeignKey | NULL, blank, SET_NULL | |
| node_id | ForeignKey | NULL, blank, SET_NULL | |
| step_id | ForeignKey | NULL, blank, SET_NULL | |
| created_at | DateTimeField | auto_now_add, db_index | |
| updated_at | DateTimeField | auto_now, db_index | |
| modified_at | DateTimeField | NULL, blank | |
| deleted_at | DateTimeField | NULL, blank | |
| deleted_by_id | ForeignKey | NULL, blank, SET_NULL | |
| status | PositiveIntegerField | default=1 | choices: STATUS_CHOICES |
| reads | PositiveIntegerField | default=0 | |
| post_count | PositiveIntegerField | default=0 | |
| reply_count | PositiveIntegerField | default=0, db_index | |
| like_count | PositiveIntegerField | default=0, db_index | |
| body_image | ImageField | NULL, blank | |
| thumbnail_image | ImageField | NULL, blank | |
| subcategory | CharField(max_length=50) | NULL, blank | choices: FAQ_CATEGORIES |

**관계:**
- topicker -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=SET_NULL)
- first_post -> ForeignKey(forum.Post, related_name='+', on_delete=SET_NULL)
- course_type -> ForeignKey(core.CourseType, related_name='+', on_delete=SET_NULL)
- node -> ForeignKey(core.Node, related_name='+', on_delete=SET_NULL)
- step -> ForeignKey(core.Step, related_name='+', on_delete=SET_NULL)
- deleted_by -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=SET_NULL)
- tags <- ManyToManyField(Tags, blank=True)
- categories <- ManyToManyField(Category, blank=True)
- attachments <- ManyToManyField(Attachment, blank=True)
- like_user_set <- ManyToManyField(AUTH_USER_MODEL, related_name='like_user_set')
- participants <- ManyToManyField(AUTH_USER_MODEL, through='TopicParticipant', related_name='participant_set')

**Choices:**
- board_type: archive=Archive, event=이벤트, notice=공지사항, faq=FAQ
- status: 1=Normal, 2=Wait Delete, 3=Complete Delete
- subcategory: payment=결제, registration=회원가입, course=수강

**Meta:** ordering = [-updated_at]

---

#### forum.forum_topicparticipant (TopicParticipant)

**파일**: `forum/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| topic_id | ForeignKey | NOT NULL, CASCADE | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| is_owner | BooleanField | default=False | |

**Custom Manager:** TopicParticipantManager (set_owner, add_participants, remove_participant)

---

#### forum.forum_post (Post)

**파일**: `forum/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| poster_id | ForeignKey | NULL, SET_NULL | |
| topic_id | ForeignKey | NOT NULL, CASCADE | |
| post_number | PositiveIntegerField | default=1 | |
| body | TextField | NOT NULL | |
| raw | TextField | NULL, blank | |
| created_at | DateTimeField | auto_now_add, db_index | |
| updated_at | DateTimeField | auto_now | |
| modified_at | DateTimeField | NULL, blank | |
| deleted_at | DateTimeField | NULL, blank | |
| deleted_by_id | ForeignKey | NULL, blank, SET_NULL | |
| status | PositiveIntegerField | default=1 | choices: STATUS_CHOICES |
| reply_to_post_number | PositiveIntegerField | NULL, blank | |
| reply_to_user_id | ForeignKey | NULL, blank, SET_NULL | |
| like_count | PositiveIntegerField | default=0, db_index | |
| reply_count | PositiveIntegerField | default=0 | |
| quote_count | PositiveIntegerField | default=0 | |
| quote_to_post | PositiveIntegerField | NULL, blank | |
| reply_quoted | BooleanField | default=False | |

**관계:**
- poster -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=SET_NULL)
- topic -> ForeignKey(forum.Topic, on_delete=CASCADE)
- deleted_by -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=SET_NULL)
- reply_to_user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=SET_NULL)
- like_user_set <- ManyToManyField(AUTH_USER_MODEL, related_name='post_like_user_set')

**Choices:**
- status: 1=Normal, 2=Complete Delete

**Meta:** ordering = [id]; index_together = [(topic, id), (poster, created_at)]

---

#### forum.forum_postarchive (PostArchive)

**파일**: `forum/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| topic_id | ForeignKey | NOT NULL, DO_NOTHING | |
| post_id | ForeignKey | NOT NULL, DO_NOTHING | |
| body | TextField | NOT NULL | |
| raw | TextField | NULL, blank | |

---

#### forum.forum_image (Image)

**파일**: `forum/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| image | ImageField | NOT NULL | upload_to='forum/upload/...' |

---

### membership app

#### membership.event_dispatch_log (EventDispatchLog)

**파일**: `membership/models.py`
**db_table**: `event_dispatch_log`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | BigIntegerField | NOT NULL | User ID |
| action | CharField(max_length=20) | NOT NULL | create or update |
| created_at | DateTimeField | default=timezone.now | |
| updated_at | DateTimeField | auto_now | |
| data | JSONField | NOT NULL | 이벤트 원본 데이터 |
| status | CharField(max_length=20) | NOT NULL | choices: EVENT_STATUS_CHOICES |
| exit_message | TextField | NULL, blank | |

**Choices:**
- status: published=Published, success=Success, failure=Failure

---

### order app

#### order.order_order (Order)

**파일**: `order/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| created | DateTimeField | auto_now_add | |
| updated | DateTimeField | auto_now | |
| paid | BooleanField | default=False | |
| coupon_id | ForeignKey | NULL, blank, PROTECT | |
| discount | IntegerField | default=0, min=0, max=1000000 | |
| is_free | BooleanField | default=False | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='+', on_delete=CASCADE)
- coupon -> ForeignKey(Coupon, related_name='order_coupon', on_delete=PROTECT)

**Meta:** ordering = [-created]

---

#### order.order_orderitem (OrderItem)

**파일**: `order/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| order_id | ForeignKey | NOT NULL, CASCADE | |
| course_id | ForeignKey | NOT NULL, PROTECT | |
| round_schedule_id | ForeignKey | NULL, blank, PROTECT | |
| price | DecimalField(10,2) | NOT NULL | 판매가 |
| original_price | DecimalField(10,2) | default=0.00 | 정가 |
| discount_rate | DecimalField(5,2) | default=0.00, min=0, max=100 | 할인율 |
| quantity | PositiveIntegerField | default=1 | |

**관계:**
- order -> ForeignKey(Order, related_name='items', on_delete=CASCADE)
- course -> ForeignKey(core.Course, related_name='order_courses', on_delete=PROTECT)
- round_schedule -> ForeignKey(core.RoundSchedule, related_name='order_schedule', on_delete=PROTECT)

---

#### order.order_ordertransaction (OrderTransaction)

**파일**: `order/models.py`

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| order_id | ForeignKey | NOT NULL, CASCADE | |
| merchant_order_id | CharField(max_length=120) | NULL, blank | |
| transaction_id | CharField(max_length=120) | NULL, blank | |
| amount | DecimalField(10,2) | NOT NULL | |
| transaction_status | CharField(max_length=30) | default='pending' | choices: TransactionStatus |
| type | CharField(max_length=120) | blank | |
| created | DateTimeField | auto_now_add | |

**관계:**
- order -> ForeignKey(Order, on_delete=CASCADE)

**Custom Manager:** OrderTransactionManager (create_new, get_transaction, create_free_transaction)

**Choices:**
- transaction_status: pending=Pending, paid=Paid, cancelled=Cancelled, failed=Failed, free=Free

**Meta:** ordering = [-created]

**Signal:** post_save -> order_payment_validation

---

### prompts app

#### prompts.prompts_prompt (Prompt)

**파일**: `prompts/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | UUIDField (PK) | default=uuid4 | |
| name | CharField(max_length=255) | NOT NULL | 프롬프트 이름 |
| content | TextField | NOT NULL | 프롬프트 내용 |
| author_id | ForeignKey | NOT NULL, CASCADE | |
| model | CharField(max_length=100) | NULL, blank | AI 모델 타입 |

**관계:**
- author -> ForeignKey(AUTH_USER_MODEL, related_name='prompts', on_delete=CASCADE)

**Meta:** ordering = [-created]

---

#### prompts.prompts_promptassociation (PromptAssociation)

**파일**: `prompts/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | UUIDField (PK) | default=uuid4 | |
| prompt_id | ForeignKey | NOT NULL, CASCADE | |
| service_category | CharField(max_length=30) | NOT NULL | 서비스 대분류 |
| service_subtype | CharField(max_length=50) | NOT NULL | 서비스 세부 유형 |
| service_id | CharField(max_length=255) | NOT NULL | 서비스 내 고유 식별자 |

**관계:**
- prompt -> ForeignKey(Prompt, related_name='associations', on_delete=CASCADE)

**Choices:**
- service_category: lms=LMS 시스템, ai=AI 서비스, chat=채팅 시스템
- service_subtype (LMS): node=노드, nodeversion=노드 버전, nodeschedule=노드 스케줄, course=코스
- service_subtype (AI): tagextractor=태그 추출기, translator=번역기

**Meta:** unique_together = (prompt, service_category, service_subtype, service_id); indexes = [service_category, service_subtype]

---

#### prompts.prompts_defaultprompt (DefaultPrompt)

**파일**: `prompts/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | UUIDField (PK) | default=uuid4 | |
| user_id | ForeignKey | NOT NULL, CASCADE | |
| service_category | CharField(max_length=30) | NOT NULL | 서비스 대분류 |
| service_subtype | CharField(max_length=50) | NOT NULL | 서비스 세부 유형 |
| service_id | CharField(max_length=255) | NOT NULL | 서비스 내 고유 식별자 |
| prompt_id | ForeignKey | NOT NULL, CASCADE | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='default_prompts', on_delete=CASCADE)
- prompt -> ForeignKey(Prompt, related_name='default_for_services', on_delete=CASCADE)

**Meta:** unique_together = (user, service_category, service_subtype, service_id)

---

### tasks app

#### tasks.tasks_notitalk (Notitalk)

**파일**: `tasks/models.py`
**상속**: TimeStampedModel

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | AutoField (PK) | NOT NULL | |
| user_id | ForeignKey | NULL, blank, CASCADE | |
| course_progrs_id | ForeignKey | NULL, blank, SET_NULL | |
| group_id | CharField(max_length=255) | NULL, blank | Identifier for group messages |
| template_id | CharField(max_length=50) | NOT NULL | |
| sent_date | DateTimeField | auto_now_add | |
| status | CharField(max_length=50) | default='PENDING' | choices: NotitalkStatus |
| additional_info | JSONField | NULL, blank | |
| created | DateTimeField | auto (TimeStamped) | |
| modified | DateTimeField | auto (TimeStamped) | |

**관계:**
- user -> ForeignKey(AUTH_USER_MODEL, related_name='notitalk_histories', on_delete=CASCADE)
- course_progrs -> ForeignKey(core.CourseProgrs, related_name='notitalk_histories', on_delete=SET_NULL)

**Choices:**
- status: PENDING=대기중, SENDING=발송 요청됨, DELETED=삭제됨, FAILED=실패, COMPLETE=발송 완료, SCHEDULED=발송 예약

---

### Django 모델 통계 요약

| 항목 | 수치 |
|------|------|
| **총 concrete 모델** | 93 |
| **Proxy 모델** | 4 (AnswerSummary, NodeProgrsSummary, StepComptSummary, EvaluationSummary) |
| **Abstract 클래스** | 1 (FileRelation) |
| **Wagtail Page 모델** | 2 (BlogIndexPage, BlogPage) |

**앱별 모델 수:**
- core: 55 모델 (최대)
- apply: 11 모델
- forum: 8 모델
- core.survey: 4 모델
- comcom: 4 모델
- order: 3 모델
- prompts: 3 모델
- attendance: 2 모델
- auths: 2 모델
- blog: 2 모델 (Wagtail)
- coupon: 1 모델
- articles: 1 모델
- membership: 1 모델
- tasks: 1 모델

---

## 16. Redis / MySQL 구성

### NestJS — Redis Cluster
- **모드**: Cluster (dev 기준 6개 노드)
- **호스트**: `redis-dev.modulabs.co.kr`, 포트 6380~6385
- **용도**: 캐시, 세션, 분산 락 (Redlock)

### Django — Redis + Celery
- **용도**: Celery 메시지 브로커, 캐시
- **백그라운드 태스크**: 27종 (이메일 발송, 비디오 처리, 알림 등)

### MySQL (폴백용)
- **호스트**: `db-wordpress.modulabs.co.kr:3306`
- **데이터베이스**: `moduflip17`
- **용도**: Redis 장애 시 분산 락 폴백

---

## 17. 사용자 역할 체계

| 시스템 | 역할 |
|--------|------|
| modulabs-backend-service | `ADMIN`, `DJANGO_SERVER`, 일반 사용자 |
| aiffel_back | `student`, `coach`, `editor`, `staff`, `local_admin`, `superuser`, `k_digital` |

---

## 18. 수강 상태 코드

### core_courseprogrs 상태 코드

| 코드 | 의미 |
|------|------|
| `Z` | 승인 대기 (Pending approval) |
| `A` | 수강 전 (Before proceeding) |
| `B` | 수강 가능 (Possible to proceed) |
| `C` | 수강 중 (Proceeding) |
| `D` | 관리자 거부 (Admin deny) |
| `F` | 환불 처리 (Refund) |
| `G` | 수강 완료 (Completion: 80%) |
| `H` | 수료 (Finish) |
| `R` | 수료 대기 (Waiting for certificate) |
| `I` | 지연 (Delay) |
| `J` | 심각한 지연 (Serious delay) |
| `S` | 스태프 (Staff account) |

---

## 19. 데이터 접근 패턴

### NestJS (modulabs-backend-service)
- **ORM**: TypeORM 0.3
- **패턴**: `BaseRepository<T>` + `@CustomRepository()` 데코레이터
- **N+1 방지**: DataLoader 사용 (`@ResolveField()` 호출 시)
- **트랜잭션**: `@Transactional()` 데코레이터 (typeorm-transactional)
- **캐싱**: `@Cacheable()` 데코레이터 + Redis
- **API**: GraphQL (Apollo Server 4) + REST
- **네이밍**: SnakeNamingStrategy (DB 컬럼은 snake_case, 코드는 camelCase)

### Django (aiffel_back)
- **ORM**: Django ORM
- **패턴**: `models.Model` + QuerySet
- **백그라운드**: Celery (27개 태스크)
- **API**: Django REST Framework (DRF)

### 마이그레이션 패턴

**NestJS:**
- 위치: `src/migration/`
- 형식: `[timestamp]-[description].ts`
- 수동 마이그레이션 (TypeORM CLI 자동 생성 미사용)

**Django:**
- 위치: `{app}/migrations/`
- 형식: Django 표준 `000X_description.py`
- 실행: `python manage.py makemigrations` / `python manage.py migrate`

### TypeORM 엔티티 패턴 예시

```typescript
@Entity({ name: 'order', schema: 'orderx' })
export class Order extends BaseEntity {
  @PrimaryColumn({ type: 'int8', generated: 'increment', transformer: new StringToNumberTransformer() })
  id: number

  @Column({ type: 'decimal', precision: 10, scale: 2 })
  totalPrice: string

  @CreateDateColumn({ type: 'timestamp with time zone' })
  createdAt: Date

  @OneToMany(() => OrderItem, item => item.order)
  items: OrderItem[]
}
```

**공통 트랜스포머:**
- `StringToNumberTransformer` -- bigint 컬럼 (int8) 처리
- Date transformer -- 타임존 처리
- Decimal transformer -- 금액 필드

### 결제 연동 (DB 관련)

| PG사 | 사용 테이블 | 비고 |
|------|------------|------|
| Portone/Iamport v1+v2 | `orderx.order`, `orderx.order_transaction`, `orderx.webhook_history` | NestJS + Django 양쪽 |
| Toss Payments | `orderx.order_transaction` | NestJS |
| Naver Payments | `orderx.order_transaction` | NestJS |

---

## 20. 환경별 DB 호스트

| 환경 | PostgreSQL Host | Redis Host | 비고 |
|------|----------------|------------|------|
| dev | `db-dev.modulabs.co.kr` | `redis-dev.modulabs.co.kr:6380-6385` | NestJS+Django 공유 가능 |
| stg | (환경변수) | (환경변수) | NestJS+Django 공유 가능 |
| prd | (환경변수, 별도 인스턴스) | (환경변수) | 완전 분리 |

### 엔티티/모델 파일 위치

**NestJS TypeORM 엔티티:**
```
src/course/entity/*.entity.ts          (~30 파일)
src/orderx/entities/*.entity.ts        (~9 파일)
src/membership/entities/*.entity.ts    (6 파일)
src/resource/entities/*.entity.ts      (13 파일)
src/lab/meta/entities/*.entity.ts      (4 파일)
src/product/entities/*.entity.ts       (1 파일)
+ 기타 모듈별 분산 엔티티 (~50개 모듈)
```

**Django 모델:**
```
core/models.py                (~55 모델)
apply/models.py               (~11 모델)
forum/models.py               (~8 모델)
core/survey/models.py         (~4 모델)
comcom/models.py              (~4 모델)
order/models.py               (~3 모델)
prompts/models.py             (~3 모델)
attendance/models.py          (~2 모델)
auths/models.py               (~2 모델)
blog/models.py                (~2 모델)
coupon/models.py              (~1 모델)
articles/models.py            (~1 모델)
membership/models.py          (~1 모델)
tasks/models.py               (~1 모델)
```

---

## 요약 통계

| 항목 | 수치 |
|------|------|
| NestJS 엔티티 | 259+ |
| PostgreSQL 스키마 | 10+ (service, public, orderx, resource, membership, class, section, biz, channeltalk 등) |
| Django 모델 (concrete) | 93 |
| Django 모델 (proxy) | 4 |
| Redis 노드 (dev) | 6 (클러스터) |
| MySQL 폴백 DB | 1 |
| TypeORM 커넥션 | 4 |
| 레거시 공유 테이블 | 50+ (public 스키마) |
| Celery 백그라운드 태스크 | 27 |

---

# 부록 A: NestJS 엔티티 상세 (컬럼/타입/관계)

> 아래는 modulabs-backend-service의 260개 TypeORM 엔티티에서 추출한 전체 컬럼, 데이터 타입, 관계 정보입니다.
> 스키마별로 그룹화되어 있습니다.

---

## A.1 service 스키마 엔티티 상세


### service.admin_action_history (AdminActionHistory)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | uuid | PK | UUID, BeforeInsert 자동생성 |
| member_id | bigint | NOT NULL | 회원 ID |
| meta_value | jsonb | NOT NULL | 메타 데이터 |
| created_at | timestamptz | NOT NULL, update:false | 생성일시 |

### service.admin_member_create_history (AdminMemberCreateHistory)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| sessionId | (default) | NOT NULL | 세션 ID |
| username | (default) | NOT NULL | 사용자명 |
| email | (default) | NOT NULL | 이메일 |
| isStaff | (default) | NOT NULL | 스태프 여부 |
| memberId | (default) | nullable | 회원 ID |
| lmsId | (default) | nullable | LMS ID |
| localSchoolId | (default) | nullable | 지역학교 ID |
| status | (default) | NOT NULL | 상태 (SUCCESS/FAILED) |
| failedReason | (default) | nullable | 실패 사유 |
| createdBy | (default) | NOT NULL | 생성자 ID |

### service.ad_banner (AdBanner)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| analyzedMeta | jsonb | nullable | 분석 메타 데이터 |

### service.ad_banner_detail (AdBannerDetail)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| banner_id | varchar(36) | NOT NULL | 배너 ID |
| main_title | varchar(255) | NOT NULL | 메인 타이틀 |
| sub_title | varchar(255) | nullable | 서브 타이틀 |
| landing_link | text | NOT NULL | 랜딩 링크 |
| utm | jsonb | nullable | UTM 파라미터 |

### service.ad_banner_image (AdBannerImage)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| banner_id | varchar(36) | NOT NULL | 배너 ID |
| key | text | NOT NULL | S3 키 |
| is_manual_upload | boolean | NOT NULL | 수동 업로드 여부 |
| is_primary | boolean | NOT NULL | 대표 이미지 여부 |
| meta | jsonb | NOT NULL | 메타 데이터 |

### service.ad_material (AdMaterial)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| type | varchar(30) | NOT NULL | 광고 소재 타입 (AdMaterialType) |
| code | varchar(255) | NOT NULL | 코드 |
| status | varchar(30) | NOT NULL | 상태 (AdMaterialStatus) |
| priority | integer | NOT NULL | 우선순위 |

### service.biz_class_order (BizClassOrder)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| admin_id | bigint | NOT NULL | 관리자 ID |
| order_pk | varchar | NOT NULL | 주문 PK |

### service.kdt_class_order (KdtClassOrder)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| admin_id | bigint | NOT NULL | 관리자 ID |
| order_pk | varchar | NOT NULL | 주문 PK |

### service.home_section (HomeSection)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| type | varchar | unique: true | 섹션 타입 |
| meta_value | jsonb | NOT NULL | 메타 데이터 |

관계: HomeSectionDetail[] ← @OneToMany

### service.home_section_detail (HomeSectionDetail)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| home_section_id | bigint | NOT NULL | FK to home_section |
| meta_value | jsonb | NOT NULL | 메타 데이터 |

관계: HomeSection → @ManyToOne (onDelete: CASCADE)

### service.notice (Notice)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| title | varchar(100) | NOT NULL | 공지 제목 |
| content | text | NOT NULL | 공지 내용 |
| target | varchar[] | NOT NULL, array | 공지 대상 (NoticeTarget[]) |
| severity | varchar(30) | NOT NULL | 심각도 (NoticeSeverity) |
| is_active | boolean | NOT NULL, default: true | 활성 여부 |
| publish_at | timestamptz | NOT NULL | 공개일시 |
| expire_at | timestamptz | nullable | 만료일시 |
| created_by | bigint | NOT NULL | 생성자 ID |
| updated_by | bigint | NOT NULL | 수정자 ID |

### service.notice_attachment (NoticeAttachment)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| notice_id | bigint | NOT NULL | 공지 FK |
| file_name | text | NOT NULL | 파일명 |
| content_type | text | nullable | MIME 타입 |
| byte_size | bigint | nullable | 파일 크기 |
| path | text | NOT NULL | 파일 경로 |

관계: Notice → @ManyToOne (onDelete: CASCADE)

### service.alimtalk_notification_history (AlimtalkNotificationHistory)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| senderNumber | varchar(20) | nullable | 발신번호 |
| recipientId | bigint | nullable | 수신자 회원 ID |
| recipientNumber | varchar(20) | NOT NULL | 수신 전화번호 |
| notificationType | varchar(20) | nullable | 알림 유형 |
| venderType | enum(AlimtalkNotificationVender) | nullable | 벤더 유형 |
| alimtalkTemplateId | bigint | NOT NULL | 알림톡 템플릿 FK |
| variables | jsonb | nullable | 템플릿 변수 |
| reserveTime | varchar(100) | nullable | 예약 시간 |
| status | enum(AlimtalkNotificationStatus) | nullable | 발송 상태 |
| exitMessage | text | nullable | 실패 메시지 |
| requestId | varchar(255) | nullable | 외부 요청 ID |
| requestAt | timestamptz | nullable | 요청 일시 |
| responseAt | timestamptz | nullable | 응답 일시 |

관계: AlimtalkTemplate → @ManyToOne

### service.alimtalk_template (AlimtalkTemplate)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| templateId | varchar | NOT NULL | 외부 템플릿 ID |
| name | varchar | NOT NULL | 템플릿 이름 |
| content | text | NOT NULL | 템플릿 내용 |
| variables | jsonb | nullable | 변수 목록 |
| type | enum(AlimtalkTemplateType) | NOT NULL, default: KAKAO | 템플릿 유형 |
| isActive | boolean | NOT NULL, default: true | 활성 여부 |

관계: AlimtalkNotificationHistory[] ← @OneToMany

### service.email_notification_history (EmailNotificationHistory)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| recipient_id | bigint | nullable | 수신자 회원 ID |
| recipient_email | varchar(255) | NOT NULL | 수신 이메일 |
| sender_email | varchar(255) | NOT NULL | 발신 이메일 |
| subject | varchar(500) | NOT NULL | 메일 제목 |
| body | text | NOT NULL | 메일 본문 |
| status | varchar(20) | NOT NULL, default: PENDING | 발송 상태 |
| message_id | varchar(255) | nullable | 외부 메시지 ID |
| exit_message | text | nullable | 실패 메시지 |
| request_at | timestamptz | nullable | 요청 일시 |
| response_at | timestamptz | nullable | 응답 일시 |

### service.sms_notification_history (SmsNotificationHistory)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| senderNumber | varchar(20) | nullable | 발신번호 |
| recipientId | bigint | nullable | 수신자 회원 ID |
| recipientNumber | varchar(20) | NOT NULL | 수신 전화번호 |
| notificationType | enum(SmsNotificationType) | nullable | SMS 유형 |
| venderType | enum(SmsNotificationVender) | nullable | 벤더 유형 |
| subject | varchar(100) | nullable | 제목 |
| message | text | NOT NULL | 메시지 본문 |
| reserveTime | varchar(100) | nullable | 예약 시간 |
| status | enum(SmsNotificationStatus) | nullable | 발송 상태 |
| exitMessage | text | nullable | 실패 메시지 |
| requestId | varchar(255) | nullable | 외부 요청 ID |
| requestAt | timestamptz | nullable | 요청 일시 |
| responseAt | timestamptz | nullable | 응답 일시 |

### service.slack_info (SlackInfo)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| message_type | varchar(255) | NOT NULL | 메시지 유형 (SlackMessageType) |
| channel_path | varchar(255) | NOT NULL | 채널 경로 |
| text_template | text | NOT NULL | 텍스트 템플릿 |

### service.slack_invitation_info (SlackInvitationInfo)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| invitation_link | varchar(255) | NOT NULL | 초대 링크 |

### service.aws_s3_file_meta (AwsS3FileMeta)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | integer | PK, auto-increment | |
| key | text | NOT NULL | S3 key |
| original_name | text | NOT NULL | 원본 파일명 |
| mime_type | varchar(255) | NOT NULL | MIME 타입 |
| size | bigint | NOT NULL | 파일 크기 |
| bucket | varchar(100) | NOT NULL | S3 버킷 |
| region | varchar(50) | NOT NULL | S3 리전 |
| created_by | bigint | nullable | 생성자 ID |
| created_at | timestamp | CreateDateColumn | 생성일시 |

### service.permanent_files (PermanentFile)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| key | text | NOT NULL, unique | S3 key |
| original_name | varchar(500) | NOT NULL | 원본 파일명 |
| mime_type | varchar(255) | NOT NULL | MIME 타입 |
| size | bigint | NOT NULL | 파일 크기 |
| bucket | varchar(100) | NOT NULL | S3 버킷 |
| status | varchar(50) | NOT NULL, default: PENDING | 상태 |
| uploaded_at | timestamptz | nullable | 업로드 일시 |
| description | text | nullable | 설명 |
| created_by | int8 | nullable | 생성자 ID |

### service.member_memo (MemberMemo)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 대상 회원 ID |
| content | text | NOT NULL | 메모 내용 |
| author_id | int8 | NOT NULL | 작성자 ID |
| deleted_at | timestamptz | nullable | 소프트 삭제 시각 |

### service.channeltalk (ChannelTalk)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| data | jsonb | NOT NULL | 채널톡 데이터 |

### service.user_enrolments_queue (UserEnrolmentsQueue)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| email | varchar | NOT NULL | 이메일 |
| member_id | bigint | NOT NULL | 회원 ID |
| lms_id | bigint | NOT NULL | LMS ID |
| is_enrolled | boolean | NOT NULL | 등록 여부 |
| local_school_id | bigint | NOT NULL | 지역학교 ID |
| enrolled_ids | varchar | NOT NULL | 등록 ID 목록 |
| session_id | varchar | NOT NULL | 세션 ID |

### service.chat_message_attachment (ChatMessageAttachment)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| chat_message_id | (default) | NOT NULL | 채팅 메시지 ID |
| file_meta_id | (default) | NOT NULL | 파일 메타 ID |
| expire_at | (default) | nullable | 만료 일시 |
| deleted_at | (default) | nullable | 삭제 일시 |

### service.chat_message (ChatMessage)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| chat_room_id | (default) | NOT NULL | 채팅방 ID |
| sender_id | (default) | NOT NULL | 발신자 ID |
| message_type | enum(ChatMessageType) | NOT NULL | 메시지 타입 |
| content | jsonb | NOT NULL | 메시지 내용 |
| deleted_at | (default) | nullable | 삭제 일시 |

### service.chat_room (ChatRoom)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| room_type | enum(ChatRoomType) | NOT NULL | 채팅방 타입 |
| code | (default) | NOT NULL | 채팅방 코드 |
| name | (default) | NOT NULL | 채팅방명 |
| thumbnail_url | (default) | nullable | 썸네일 URL |
| status | (default) | NOT NULL | 상태 (ChatRoomStatus) |
| created_by | (default) | nullable | 생성자 ID |

### service.chat_room_meta (ChatRoomMeta)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| chat_room_id | (default) | NOT NULL | 채팅방 ID |
| last_message_at | (default) | NOT NULL | 마지막 메시지 일시 |

### service.chat_room_participant (ChatRoomParticipant)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| chat_room_id | (default) | NOT NULL | 채팅방 ID |
| member_id | bigint | NOT NULL | 회원 ID |
| role | varchar(30) | NOT NULL | 역할 (ChatParticipantRole) |
| joined_at | timestamptz | NOT NULL | 참여 일시 |
| left_at | timestamptz | nullable | 퇴장 일시 |
| last_read_message_id | varchar(36) | nullable | 마지막 읽은 메시지 ID |

### service.category (Category - Post)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 카테고리명 |
| slug | varchar(255) | NOT NULL | URL slug |
| description | text | NOT NULL, default: '' | 설명 |
| is_active | boolean | NOT NULL, default: true | 활성 여부 |
| display_order | int | NOT NULL, default: 0 | 표시 순서 |
| deleted_at | timestamptz | nullable | 삭제일 (soft delete) |

### service.post (Post)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | bigint | NOT NULL | 작성자 회원 ID |
| title | varchar(255) | NOT NULL | 제목 |
| content | text | NOT NULL | 본문 |
| type | varchar | NOT NULL | 게시물 유형 |
| image_url | varchar | NOT NULL, default: '' | 대표 이미지 URL |
| status | varchar | NOT NULL, default: DRAFT | 상태 (PostStatus) |
| access_level | varchar | NOT NULL | 접근 수준 (PostAccessLevel) |
| published_at | timestamptz | NOT NULL | 공개 일시 |
| deleted_at | timestamptz | nullable | 삭제 일시 (soft delete) |
| slug | varchar(255) | NOT NULL, default: '' | SEO URL slug |
| description | varchar(255) | NOT NULL, default: '' | SEO 설명 |

관계: PostView ← @OneToOne, PostLike[] ← @OneToMany, Comment[] ← @OneToMany, PostMapping ← @OneToOne, PostAttachment[] ← @OneToMany

### service.post_view (PostView)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| post_id | int8 | NOT NULL | 게시물 FK |
| view_count | int | NOT NULL | 조회수 |

관계: Post → @OneToOne

### service.post_like (PostLike)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |
| post_id | int8 | NOT NULL | 게시물 FK |

제약: UNIQUE(post_id, member_id)

### service.post_attachment (PostAttachment)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| post_id | int8 | NOT NULL | 게시물 FK |
| aws_s3_file_meta_id | int8 | NOT NULL | S3 파일 메타 FK |
| attachment_type | varchar(20) | NOT NULL | 첨부 유형 (PostAttachmentType) |

### service.post_mapping (PostMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| post_id | int8 | NOT NULL | 게시물 FK |
| entity_id | int8 | NOT NULL | 매핑 대상 엔티티 ID |
| entity_type | varchar(255) | NOT NULL | 매핑 대상 엔티티 타입 |

### service.post_type (PostType)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 타입명 |
| display_name | varchar(255) | NOT NULL | 표시명 |
| write_open | boolean | NOT NULL | 작성 가능 여부 |
| is_active | boolean | NOT NULL | 활성 여부 |

### service.post_seo_recommend_history (PostSeoRecommendHistory)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| postId | bigint | NOT NULL | 게시물 ID |
| score | int | NOT NULL | SEO 점수 |
| recommendInfo | jsonb | NOT NULL | 추천 정보 |
| triggeredBy | bigint | NOT NULL | 실행자 회원 ID |

### service.comment (Comment - Post)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 작성자 회원 ID |
| post_id | int8 | NOT NULL | 게시물 FK |
| parent_comment_id | int8 | nullable | 부모 댓글 FK (자기참조) |
| content | text | NOT NULL | 댓글 내용 |
| is_blocked | boolean | NOT NULL, default: false | 차단 여부 |
| deleted_at | timestamptz | nullable | 삭제일 (soft delete) |

관계: Post → @ManyToOne, Comment → @ManyToOne(부모), Comment[] ← @OneToMany(자식), CommentLike[] ← @OneToMany

### service.comment_like (CommentLike)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |
| comment_id | int8 | NOT NULL | 댓글 FK |

제약: UNIQUE(member_id, comment_id)

### service.product (Product)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| original_price | decimal(10,2) | NOT NULL | 상품 원가 |
| sale_price | decimal(10,2) | NOT NULL | 상품 판매가 |
| status | varchar | NOT NULL | 상품 상태 |
| entity_id | varchar | nullable | 참조 ID |
| entity_type | varchar | nullable | 참조 타입 |

### service.momo_lab_mapping (MomoLabMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| lab_id | int8 | unique | 랩 ID |
| momo_id | int8 | unique | 모모 ID |

### service.survey_option (SurveyOption)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| type | varchar(50) | NOT NULL | 설문 타입 |
| meta_value | jsonb | NOT NULL | 메타 데이터 |

### service.tag (Tag)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| value | varchar(255) | UNIQUE, NOT NULL | 태그 값 |

### service.tag_mapping (TagMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| entity_id | bigint | NOT NULL | 엔티티 ID |
| entity_type | varchar(255) | NOT NULL | 엔티티 타입 |
| tag_id | bigint | NOT NULL | 태그 FK |

제약: UNIQUE(entity_id, entity_type, tag_id)
관계: Tag → @OneToOne

### service.service_category (ServiceCategory)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| code | varchar(50) | UNIQUE, NOT NULL | 서비스 카테고리 코드 |
| name | varchar(100) | NOT NULL | 이름 |
| description | text | nullable | 설명 |

### service.service_purpose (ServicePurpose)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| title | varchar(100) | NOT NULL | 서비스 목적명 |
| description | text | nullable | 설명 |

관계: ServicePurposeTagMapping[] ← @OneToMany

### service.service_purpose_member_mapping (ServicePurposeMemberMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| purpose_id | int | NOT NULL | 서비스 목적 FK |
| member_id | int | NOT NULL | 회원 ID |

### service.service_purpose_tag_mapping (ServicePurposeTagMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| purpose_id | int | NOT NULL | 서비스 목적 FK |
| service_tag_id | int | NOT NULL | 서비스 태그 FK |

### service.service_tag (ServiceTag)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| code | varchar(50) | UNIQUE, NOT NULL | 서비스 태그 코드 |
| name | varchar(100) | NOT NULL | 이름 |
| description | text | nullable | 설명 |
| category_id | int | NOT NULL | 서비스 카테고리 FK |

관계: ServiceCategory → @ManyToOne

### service.settlement_history (SettlementHistory)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| tableName | varchar(100) | NOT NULL | 테이블 이름 |
| recordId | varchar(36) | NOT NULL | 레코드 ID |
| changeType | varchar(20) | NOT NULL | 변경 유형 |
| changedBy | bigint | nullable | 변경자 ID |
| data | jsonb | nullable | 변경 데이터 |

### service.settlement_income_tax (SettlementIncomeTax)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| taxType | varchar(40) | UNIQUE, NOT NULL | 세금 유형 |
| label | varchar(100) | NOT NULL | 라벨 |
| defaultTaxRate | numeric(5,2) | NOT NULL | 기본 소득세율 |
| defaultLocalTaxRate | numeric(5,2) | NOT NULL | 기본 지방세율 |
| description | text | NOT NULL | 설명 |

### service.settlement_request (SettlementRequest)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | varchar(100) | PK (문자열) | 정산 요청 ID |
| batch_id | varchar(36) | NOT NULL | 배치 ID |
| status | varchar(50) | NOT NULL | 정산 상태 (SettlementRequestStatus) |
| status_reason | varchar(255) | nullable | 상태 사유 |
| paid_amount | numeric(15,2) | NOT NULL | 결제 금액 |
| supply_amount | numeric(15,2) | NOT NULL | 공급가 |
| output_vat_amount | numeric(15,2) | NOT NULL | 매출 부가세 |
| settlement_amount | numeric(15,2) | NOT NULL | 정산 대상 금액 |
| income_tax_type | varchar(40) | NOT NULL | 소득세 유형 |
| income_tax_rate | numeric(5,2) | NOT NULL | 소득세율 |
| income_tax_amount | numeric(15,2) | NOT NULL | 소득세 금액 |
| local_tax_rate | numeric(5,2) | NOT NULL | 지방세율 |
| local_tax_amount | numeric(15,2) | NOT NULL | 지방세 금액 |
| input_vat_amount | numeric(15,2) | NOT NULL | 매입 부가세 |
| actual_settlement_amount | numeric(15,2) | NOT NULL | 실수령 금액 |
| scheduled_payment_date | date | NOT NULL | 예정 지급일 |
| completed_at | timestamptz | nullable | 완료 일시 |
| completed_by | bigint | nullable | 완료 처리자 ID |
| additional_meta | jsonb | nullable | 추가 메타 정보 |
| created_at | timestamptz | CreateDateColumn | 생성일 |
| modified_at | timestamptz | UpdateDateColumn | 수정일 |

관계: SettlementRequestPayee ← @OneToOne

### service.settlement_request_payee (SettlementRequestPayee)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| request_id | varchar(100) | NOT NULL | 정산 요청 FK |
| type | varchar(30) | NOT NULL | 정산 유형 (개인/법인) |
| name | varchar(100) | NOT NULL | 수령인 이름 |
| registration_number | varchar(100) | NOT NULL | 주민/사업자번호 |
| business_registration_number | varchar(100) | nullable | 사업자등록번호 |
| nation | varchar(20) | NOT NULL | 국가 |
| bank_code | varchar(30) | NOT NULL | 은행 코드 |
| bank_account | varchar(100) | NOT NULL | 계좌 번호 |
| account_holder | varchar(100) | NOT NULL | 예금주 |
| encryption_key_version | varchar(20) | NOT NULL | 암호화 키 버전 |
| address | varchar(255) | NOT NULL | 주소 |
| address_detail | varchar(255) | NOT NULL | 상세 주소 |
| business_name | varchar(200) | nullable | 상호명 |
| representative_name | varchar(100) | nullable | 대표자명 |
| business_start_date | date | nullable | 개업일 |

관계: SettlementRequest → @OneToOne

### service.short_urls (ShortUrl)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK, auto-increment | |
| code | varchar(32) | UNIQUE, NOT NULL | 단축 코드 |
| target_url | text | NOT NULL | 대상 URL |
| is_active | boolean | default: true | 활성 여부 |
| start_at | timestamptz | nullable | 시작일 |
| end_at | timestamptz | nullable | 종료일 |
| tags | text[] | default: ARRAY[]::TEXT[] | 태그 배열 |
| clicks_total | bigint | default: 0 | 총 클릭수 |
| last_clicked_at | timestamptz | nullable | 마지막 클릭 일시 |
| member_id | bigint | nullable | 생성자 ID |
| created_at | timestamptz | CreateDateColumn | |
| updated_at | timestamptz | UpdateDateColumn | |

### service.short_url_visits (ShortUrlVisit)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK, auto-increment | |
| short_url_id | bigint | NOT NULL | 단축 URL FK |
| clicked_at | timestamptz | CreateDateColumn | 클릭 일시 |
| source_key | text | NOT NULL | 소스 키 |
| referrer_url | text | nullable | 리퍼러 URL |
| user_agent | text | nullable | User Agent |
| ip_hash | text | nullable | IP 해시 |

관계: ShortUrl → @ManyToOne (onDelete: CASCADE)

### service.short_url_visit_daily (ShortUrlVisitDaily) — 복합 PK
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| short_url_id | bigint | PK | 단축 URL FK |
| date | date | PK | 날짜 |
| source_key | text | PK | 소스 키 |
| clicks | bigint | default: 0 | 클릭수 |
| first_visit_at | timestamptz | nullable | 첫 방문 |
| last_visit_at | timestamptz | nullable | 마지막 방문 |

관계: ShortUrl → @ManyToOne (onDelete: CASCADE)

### service.momo_settlement_processed_event_log (MomoSettlementProcessedEventLog)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| status | varchar | NOT NULL | 상태 |
| payload | jsonb | nullable | 페이로드 |


---

## A.2 public 스키마 엔티티 상세

### public.apply_applicationformtemplate (ApplicationFormTemplate)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| title | varchar(100) | NOT NULL | 제목 |
| schema | jsonb | NOT NULL | 폼 스키마 |
| version | integer | NOT NULL, UNIQUE(course_semester_id) | 버전 |
| is_active | boolean | NOT NULL | 활성 여부 |
| description | text | nullable | 설명 |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| course_semester_id | int8 | NOT NULL | FK |

관계: CourseSemester → @ManyToOne

### public.apply_applicationform (ApplicationForm)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| name | varchar(10) | nullable | 이름 |
| name_chosung | varchar(10) | NOT NULL | 이름 초성 |
| email | varchar(254) | nullable | 이메일 |
| phone_number | varchar(13) | nullable | 전화번호 |
| birth | date | nullable | 생년월일 |
| course | varchar(30) | nullable | 과정 |
| introduction | text | default: ' ' | 자기소개 |
| admin_note | text | nullable | 관리자 노트 |
| nb_card_yn | boolean | nullable | 내일배움카드 여부 |
| support_path | varchar(50) | nullable | 지원 경로 |
| application_form_check_yn | boolean | nullable | 지원서 확인 |
| application_form_pass_yn | boolean | nullable | 서류 통과 |
| interview_guide_yn | boolean | nullable | 면접 안내 |
| interview_attend_yn | boolean | nullable | 면접 참석 |
| interview_pass_yn | boolean | nullable | 면접 통과 |
| admission_step | integer | NOT NULL, default: 0 | 입학 단계 |
| status | varchar(2) | NOT NULL | 상태 |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| interview_date | timestamptz | nullable | 면접 일시 |
| online_semester | integer | NOT NULL | 온라인 학기 |
| portfolio_link | varchar(500) | nullable | 포트폴리오 링크 |
| member_id | int8 | nullable | 회원 ID |
| member_uuid | varchar(255) | nullable | 회원 UUID |
| extra_answer | jsonb | nullable | 추가 답변 |
| application_form_template_id | int8 | nullable | 지원서 템플릿 FK |

### public.apply_order (ApplyOrder)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |
| application_form_id | int8 | NOT NULL | 지원서 ID |
| item_name | varchar(255) | NOT NULL | 상품명 |
| status | varchar(50) | NOT NULL | 주문 상태 |
| paid_at | timestamptz | nullable | 결제 일시 |
| cancelled_at | timestamptz | nullable | 취소 일시 |

### public.apply_order_transaction (ApplyOrderTransaction)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| apply_order_id | int8 | nullable | 지원 주문 FK |
| order_pk | varchar(255) | NOT NULL | 주문 PK |

### public.apply_coursegroup (CourseGroup)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| code | varchar(20) | UNIQUE, NOT NULL | 코드 |
| name | varchar(50) | NOT NULL | 이름 |
| description | text | NOT NULL | 설명 |
| order | smallint | NOT NULL | 정렬 순서 |
| is_active | boolean | NOT NULL | 활성 여부 |

### public.apply_coursesemester (CourseSemester)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| course | varchar(255) | NOT NULL, UNIQUE(semester) | 과정 |
| semester | integer | NOT NULL, UNIQUE(course) | 학기 |
| start_date | date | NOT NULL | 시작일 |
| end_date | date | NOT NULL | 종료일 |
| is_active | boolean | NOT NULL | 활성 여부 |
| sale_price | integer | nullable | 판매가 |
| course_start_date | date | nullable | 과정 시작일 |
| course_end_date | date | nullable | 과정 종료일 |

관계: ApplicationFormTemplate[] ← @OneToMany

### public.apply_coursetype (CourseType)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| code | varchar(20) | UNIQUE | 코드 |
| name | varchar(50) | NOT NULL | 이름 |
| description | text | NOT NULL | 설명 |
| order | smallint | NOT NULL | 정렬 |
| is_active | boolean | default: true | 활성 여부 |
| course_group_id | int8 | nullable | 과정 그룹 FK |
| localschool_id | int8 | nullable | 지역학교 FK |
| main_title | varchar(100) | nullable | 메인 타이틀 |
| is_display | boolean | default: true | 노출 여부 |

### public.core_course (Course)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| title | varchar(200) | NOT NULL | 강좌 제목 |
| abstract | text | NOT NULL | 요약 |
| calendar_type | integer | NOT NULL | 캘린더 유형 |
| local_school_id | int8 | NOT NULL | 지역학교 FK |
| order | smallint | NOT NULL | 정렬 |
| color | varchar(18) | NOT NULL | 색상 |
| course_type_id | int8 | NOT NULL | 과정 유형 FK |
| available_display | boolean | NOT NULL | 표시 가능 |
| available_order | boolean | NOT NULL | 주문 가능 |
| image | varchar(100) | NOT NULL | 이미지 |
| price | numeric(10,2) | NOT NULL | 가격 |
| slug | varchar(200) | UNIQUE, NOT NULL | URL slug |
| stock | integer | NOT NULL | 재고 |
| lecture_type | varchar(30) | NOT NULL | 강의 유형 |
| is_cloud_used | boolean | NOT NULL | 클라우드 사용 |
| level | varchar(13) | NOT NULL | 수준 |
| node_count | integer | NOT NULL | 노드 수 |

관계: Enrol[] ← @OneToMany, Onlinecourse ← @OneToOne, RoundSchedule[] ← @OneToMany, SubjectCourseRelation[] ← @OneToMany, CourseNodeVersionRelation[] ← @OneToMany

### public.core_onlinecourse (Onlinecourse)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| course_ptr_id | bigint | PK (FK to core_course) | |
| duration_type | varchar(10) | NOT NULL | 기간 유형 |
| duration_value | integer | nullable | 기간 값 |
| summary | text | NOT NULL | 요약 |
| discount_rate | numeric(5,2) | nullable | 할인율 |
| selling_price | numeric(10,2) | NOT NULL | 판매가 |
| is_government_funded | boolean | NOT NULL | 국비 여부 |
| is_subject | boolean | NOT NULL | 과목 여부 |
| learning_tool | varchar(50) | nullable | 학습 도구 |
| cloud_usage_duration | integer | nullable | 클라우드 사용 기간 |
| contents | text | NOT NULL | 콘텐츠 |
| digital_friendly | integer | NOT NULL | 디지털 친화도 |
| view_count | integer | NOT NULL | 조회수 |

관계: Course → @OneToOne, Bookmark[] ← @OneToMany, Labeltaggeditem[] ← @OneToMany, OnlinecourseCategories[] ← @OneToMany, RoundSchedule[] ← @OneToMany

### public.core_node (Node)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| title | varchar(100) | NOT NULL | 노드 제목 |
| abstract | text | NOT NULL | 요약 |
| is_lecture | boolean | NOT NULL | 강의 여부 |
| is_project | boolean | NOT NULL | 프로젝트 여부 |
| is_tutorial | boolean | NOT NULL | 튜토리얼 여부 |
| is_aico | boolean | NOT NULL | AI코 여부 |
| difficulty | varchar(20) | nullable | 난이도 |

### public.core_nodeversion (NodeVersion)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| version | smallint | NOT NULL, UNIQUE(node_id) | 버전 |
| created_on | timestamptz | NOT NULL | 생성일 |
| author_id | int8 | NOT NULL | 작성자 ID |
| node_id | int8 | NOT NULL, UNIQUE(version) | 노드 FK |
| docker_image_id | int8 | nullable | 도커 이미지 ID |
| storage_path | varchar(255) | nullable | 스토리지 경로 |
| use_gpu | boolean | NOT NULL | GPU 사용 |
| use_openai_api_key | boolean | NOT NULL | OpenAI API 키 사용 |
| resource_slug | varchar | nullable | 리소스 슬러그 |
| metadata | jsonb | NOT NULL, default: {} | 메타데이터 |

관계: Node → @ManyToOne, NodeSchedule[] ← @OneToMany, Step[] ← @OneToMany, CourseNodeVersionRelation[] ← @OneToMany

### public.core_step (Step)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| order | smallint | NOT NULL | 순서 |
| title | varchar(100) | NOT NULL | 단계 제목 |
| is_code | boolean | NOT NULL | 코드 여부 |
| url | varchar(255) | NOT NULL | URL |
| tag | text | nullable | 태그 |
| node_version_id | int8 | NOT NULL | 노드 버전 FK |
| estimate_time | jsonb | NOT NULL | 예상 시간 |
| content | jsonb | nullable | 콘텐츠 |
| has_quiz | boolean | NOT NULL | 퀴즈 유무 |
| has_video | boolean | NOT NULL | 비디오 유무 |

관계: NodeVersion → @ManyToOne, StepCompt[] ← @OneToMany

### public.core_enrol (Enrol)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| enrol_start_date | timestamptz | NOT NULL | 등록 시작일 |
| enrol_end_date | timestamptz | NOT NULL | 등록 종료일 |
| course_id | int8 | NOT NULL | 강좌 FK |
| is_schedule | boolean | NOT NULL | 스케줄 여부 |
| description | text | NOT NULL | 설명 |
| service_type | varchar(1) | NOT NULL | 서비스 유형 |
| require_attendance | boolean | NOT NULL | 출석 필수 |
| training_id | varchar(20) | NOT NULL | 훈련 ID |
| training_round_number | integer | NOT NULL | 훈련 회차 |
| hrd_information_id | int8 | nullable | HRD 정보 FK |
| member_group_id | int8 | nullable | 멤버 그룹 ID |
| training_time | interval | nullable | 훈련 시간 |

관계: Course → @ManyToOne, HrdInformation → @ManyToOne, UserEnrolments[] ← @OneToMany

### public.core_userenrolments (UserEnrolments)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| start_time | timestamptz | nullable | 시작 시간 |
| end_time | timestamptz | nullable | 종료 시간 |
| enrol_id | int8 | UNIQUE(user_id, retake_status) | 등록 FK |
| user_id | int8 | UNIQUE(enrol_id, retake_status) | 사용자 ID |
| retake_status | integer | UNIQUE(enrol_id, user_id), default: 0 | 재수강 상태 |
| subject_id | int8 | nullable | 과목 ID |
| status | varchar(20) | NOT NULL, default: ACTIVE | 상태 |

관계: Enrol → @ManyToOne, NodeProgrs[] ← @OneToMany, CourseProgrs ← @OneToOne

### public.core_courseprogrs (CourseProgrs)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| status | varchar(1) | NOT NULL | 수강 상태 (A~S) |
| status_a_time ~ status_z_time | timestamptz | nullable | 각 상태 전환 시각 |
| user_enrolments_id | int8 | NOT NULL | 수강등록 FK |

관계: UserEnrolments → @OneToOne

### public.core_nodeprogrs (NodeProgrs)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| status | varchar(1) | NOT NULL | 노드 상태 |
| status_a_time ~ status_h_time | timestamptz | nullable | 각 상태 전환 시각 |
| coach_id | int8 | NOT NULL | 코치 ID |
| comment | text | nullable | 코멘트 |
| user_enrolments_id | int8 | NOT NULL, unique | 수강등록 FK |
| node_schedule_id | int8 | nullable, unique | 노드 스케줄 FK |
| last_accessed_at | timestamptz | nullable | 마지막 접근 |

관계: NodeSchedule → @ManyToOne, UserEnrolments → @ManyToOne

### public.core_nodeschedule (NodeSchedule)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| start_time | timestamptz | nullable | 시작 시간 |
| estimate_time | interval | NOT NULL | 예상 시간 |
| enrol_id | int8 | NOT NULL | 등록 FK |
| node_id | int8 | nullable | 노드 FK |
| end_time | timestamptz | nullable | 종료 시간 |
| node_version_id | int8 | NOT NULL | 노드 버전 FK |

관계: NodeVersion → @ManyToOne, NodeProgrs[] ← @OneToMany

### public.core_stepcompt (StepCompt)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| status | varchar(1) | NOT NULL | 완료 상태 |
| start_time | timestamptz | NOT NULL | 시작 시간 |
| end_time | timestamptz | NOT NULL | 종료 시간 |
| node_version_id | int8 | NOT NULL, UNIQUE(step_id, user_id) | 노드 버전 ID |
| step_id | int8 | NOT NULL, UNIQUE(node_version_id, user_id) | 단계 FK |
| user_id | int8 | NOT NULL, UNIQUE(node_version_id, step_id) | 사용자 ID |

관계: Step → @ManyToOne

### public.core_learning_time (LearningTime)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| last_ping_at | timestamptz | NOT NULL | 마지막 핑 |
| total_duration_seconds | int | NOT NULL, default: 0 | 누적 학습 시간(초) |
| node_progrs_id | int8 | NOT NULL | 노드 진도 FK |

### public.core_subject (Subject)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| title | varchar | NOT NULL | 과목명 |
| created_at | timestamptz | NOT NULL | 생성일 |
| service_type | varchar(50) | nullable | 서비스 유형 |

관계: SubjectCourseRelation[] ← @OneToMany

### public.core_subjectcourserelation (SubjectCourseRelation)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| order | smallint | NOT NULL | 순서 |
| course_id | int8 | NOT NULL | 강좌 FK |
| subject_id | int8 | NOT NULL | 과목 FK |

### public.core_coursenodeversionrelation (CourseNodeVersionRelation)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| order | smallint | NOT NULL | 순서 |
| course_id | int8 | NOT NULL, UNIQUE(node_version_id) | 강좌 FK |
| node_version_id | int8 | NOT NULL, UNIQUE(course_id) | 노드 버전 FK |

### public.core_evaluation (Evaluation)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| score | int2 | NOT NULL | 평가 점수 |
| rubric_id | int8 | NOT NULL | 루브릭 FK |
| node_progrs_id | int8 | NOT NULL | 노드 진도 FK |

### public.core_rubric (Rubric)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| order | smallint | NOT NULL | 순서 |
| metric | text | nullable | 평가 지표 |
| node_id | int8 | NOT NULL | 노드 FK |

관계: RubricCategory[] ← @OneToMany, Evaluation ← @OneToOne

### public.core_rubriccategory (RubricCategory)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| order | smallint | NOT NULL | 순서 |
| score | integer | NOT NULL | 점수 |
| eval_standard | text | nullable | 평가 기준 |
| rubric_id | int8 | NOT NULL | 루브릭 FK |

### public.core_roundschedule (RoundSchedule)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| start_date | timestamptz | NOT NULL | 시작일 |
| end_date | timestamptz | NOT NULL | 종료일 |
| round_number | integer | NOT NULL | 회차 |
| is_available | boolean | NOT NULL | 가용 여부 |
| course_id | bigint | NOT NULL | 강좌 FK |
| payment_start_date | timestamptz | nullable | 결제 시작일 |
| payment_end_date | timestamptz | nullable | 결제 종료일 |

### public.core_usersubmission (UserSubmission)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| page_slug | varchar(255) | NOT NULL | 페이지 슬러그 |
| submit_type | varchar(10) | NOT NULL | 제출 유형 |
| submit_data | text | nullable | 제출 데이터 |
| meta_data | jsonb | nullable | 메타 데이터 |
| submit_block_id | varchar(36) | NOT NULL | 제출 블록 ID |
| submit_time | timestamptz | UpdateDateColumn | 제출 시간 |
| user_id | int8 | NOT NULL | 사용자 ID |
| node_id | int8 | NOT NULL | 노드 ID |
| node_version_id | int8 | NOT NULL | 노드 버전 ID |
| block_order | integer | NOT NULL | 블록 순서 |

관계: UserSubmissionFile[] ← @OneToMany

### public.core_usersubmissionfile (UserSubmissionFile)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| file_id | int8 | NOT NULL | 파일 FK |
| user_submission_id | int8 | NOT NULL | 제출 FK |

### public.core_file (File)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| user_file_name | varchar(255) | NOT NULL | 사용자 파일명 |
| path | varchar(255) | NOT NULL | 경로 |
| size | bigint | NOT NULL | 크기 |
| is_deleted | boolean | NOT NULL, default: false | 삭제 여부 |

### public.core_localschool (LocalSchool)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| title | varchar(100) | NOT NULL | 학교명 |
| abstract | text | NOT NULL | 설명 |
| country | varchar(2) | NOT NULL | 국가 코드 |
| city | varchar(30) | NOT NULL | 도시 |
| type | varchar(3) | NOT NULL | 유형 |
| public | boolean | NOT NULL | 공개 여부 |

### public.core_user (CoreUser)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| username | varchar | NOT NULL | 사용자명 |
| firstName | varchar | NOT NULL | 이름 |
| lastName | varchar | NOT NULL | 성 |
| email | varchar | NOT NULL | 이메일 |
| isCoach | boolean | default: false | 코치 여부 |
| isActive | boolean | default: true | 활성 여부 |
| isEditor | boolean | NOT NULL | 에디터 여부 |
| isCloud | boolean | NOT NULL | 클라우드 여부 |
| isStaff | boolean | NOT NULL | 스태프 여부 |
| isStudent | boolean | NOT NULL | 학생 여부 |
| localAdmin | boolean | default: false | 로컬 관리자 |
| k_digital | boolean | NOT NULL | K-Digital 여부 |
| bio | varchar | NOT NULL | 자기소개 |
| photo | varchar | NOT NULL | 프로필 사진 |
| lastLogin | timestamptz | NOT NULL | 마지막 로그인 |
| dateJoined | timestamptz | NOT NULL | 가입일 |
| accountStatus | varchar | NOT NULL | 계정 상태 |

관계: CoreUserLocalSchool[] ← @OneToMany

### public.core_userprivacy (UserPrivacy)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| unique_key | varchar(88) | nullable | 본인인증 고유키 |
| birth | date | nullable | 생년월일 |
| address1 | varchar(250) | nullable | 주소 |
| address2 | varchar(250) | nullable | 상세 주소 |
| mkt_agreement_yn | boolean | NOT NULL | 마케팅 동의 |
| user_id | int8 | NOT NULL | 사용자 FK |
| gender | varchar(1) | NOT NULL | 성별 |
| phone_number | varchar(13) | NOT NULL | 전화번호 |
| nb_card_yn | boolean | NOT NULL | 내일배움카드 |

### public.core_userlogentry (UserLogEntry)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| action | varchar(64) | NOT NULL | 액션 |
| datetime | timestamptz | NOT NULL | 일시 |
| ip | inet | nullable | IP |
| user_agent | varchar(300) | NOT NULL | User Agent |
| user_id | int8 | NOT NULL | 사용자 ID |
| user_enrolments_id | int8 | nullable | 수강등록 ID |

### public.core_hrdinformation (HrdInformation)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| title | varchar(255) | NOT NULL | 제목 |
| trainingStartDate | date | NOT NULL | 훈련 시작일 |
| trainingEndDate | date | NOT NULL | 훈련 종료일 |
| applicants | int | NOT NULL | 신청자 수 |
| capacity | int | NOT NULL | 정원 |
| company | varchar(255) | NOT NULL | 기관 |
| roundNumber | int | NOT NULL | 회차 |
| trainingId | varchar(255) | NOT NULL | 훈련 ID |
| trainingType | varchar(255) | NOT NULL | 훈련 유형 |
| tuition | numeric(10,2) | NOT NULL | 수강료 |

### public.core_category (Category)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| name | varchar(255) | NOT NULL | 카테고리명 |
| description | text | nullable | 설명 |
| image | varchar(100) | nullable | 이미지 |

### public.taggit_tag (TaggitTag)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | integer | PK | |
| name | varchar(100) | UNIQUE, NOT NULL | 태그명 |
| slug | varchar(100) | UNIQUE, NOT NULL | 슬러그 |

### public.order_order (LegacyOrder)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| paid | boolean | NOT NULL | 결제 완료 |
| discount | integer | NOT NULL | 할인 금액 |
| coupon_id | bigint | nullable | 쿠폰 FK |
| user_id | bigint | NOT NULL | 사용자 ID |
| is_free | boolean | NOT NULL | 무료 여부 |

관계: LegacyOrderItem ← @OneToOne, LegacyOrderTransaction ← @OneToOne

### public.order_orderitem (LegacyOrderItem)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| price | decimal(10,2) | NOT NULL | 가격 |
| quantity | integer | NOT NULL | 수량 |
| course_id | bigint | NOT NULL | 코스 FK |
| order_id | bigint | NOT NULL | 주문 FK |
| round_schedule_id | bigint | nullable | 회차 스케줄 FK |
| discount_rate | decimal(5,2) | NOT NULL | 할인율 |
| original_price | decimal(10,2) | NOT NULL | 원가 |

### public.order_ordertransaction (LegacyOrderTransaction)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK | |
| merchant_order_id | varchar(120) | nullable | 상점 주문 ID |
| transaction_id | varchar(120) | nullable | 트랜잭션 ID |
| amount | decimal(10,2) | NOT NULL | 금액 |
| transaction_status | varchar(30) | NOT NULL | 거래 상태 |
| type | varchar(120) | NOT NULL | 거래 유형 |
| order_id | bigint | NOT NULL | 주문 FK |

### public.board (Board)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| type | enum(BoardType) | NOT NULL | 게시판 타입 |
| user_group_id | bigint | NOT NULL | 사용자 그룹 FK |
| name | varchar(50) | NOT NULL | 게시판명 |
| description | text | nullable | 설명 |
| active | boolean | default: true | 활성 여부 |

관계: UserGroup → @ManyToOne

### public.post (Post - Board)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| board_id | bigint | NOT NULL | 게시판 FK |
| author_id | bigint | NOT NULL | 작성자 FK |
| title | varchar(200) | NOT NULL | 제목 |
| content | text | NOT NULL | 내용 |
| deleted | boolean | default: false | 삭제 여부 |
| audience_type | varchar(200) | nullable | 대상 유형 |
| target_user_id | bigint | nullable | 대상 사용자 |
| inquiry_category | varchar(50) | nullable | 문의 카테고리 |
| completed | boolean | default: false | 완료 여부 |

### public.comment (Comment - Board)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| post_id | bigint | NOT NULL | 게시글 FK |
| author_id | bigint | NOT NULL | 작성자 FK |
| content | text | NOT NULL | 댓글 내용 |
| deleted | boolean | default: false | 삭제 여부 |
| parent_id | bigint | nullable | 부모 댓글 FK (자기참조) |

### public.attachment (Attachment)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| post_id | bigint | nullable | 게시글 FK |
| comment_id | bigint | nullable | 댓글 FK |
| type | varchar(30) | NOT NULL | 파일 타입 |
| path | text | NOT NULL | 파일 경로 |
| original_name | varchar(255) | nullable | 원본 파일명 |
| size | bigint | nullable | 파일 크기 |

### public.user_group (UserGroup)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(100) | UNIQUE, NOT NULL | 그룹명 |
| description | varchar(255) | NOT NULL | 설명 |
| service_type | varchar(20) | default: CAMP | 서비스 유형 |
| localschool_id | bigint | NOT NULL | 지역학교 FK |
| course_semester_id | bigint | nullable | 과정 학기 FK |
| is_old_lms | boolean | default: false | 구 LMS 여부 |
| is_renew_enrol | boolean | default: true | 신규 등록 여부 |

관계: LocalSchool → @ManyToOne, CourseSemester → @ManyToOne

### public.user_group_mapping (UserGroupMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| user_id | bigint | nullable | 사용자 FK |
| user_group_id | bigint | NOT NULL | 그룹 FK |
| role | varchar(30) | NOT NULL | 역할 |
| status | varchar(30) | default: ACTIVE | 상태 |
| enrollment_status | varchar(30) | default: IN_PROGRESS | 등록 상태 |
| dropout_at | timestamptz | nullable | 중도탈락 일시 |
| dropout_reason | varchar(255) | nullable | 탈락 사유 |
| cloud_begin_at | timestamptz | nullable | 클라우드 시작 |
| cloud_end_at | timestamptz | nullable | 클라우드 종료 |

### public.user_group_course_mapping (UserGroupCourseMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| user_group_id | bigint | NOT NULL | 그룹 FK |
| course_id | bigint | NOT NULL | 강좌 FK |
| order | int | NOT NULL | 순서 |

### public.trainee_comments (TraineeComments)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| service_type | varchar(30) | NOT NULL | 서비스 타입 |
| user_group_id | bigint | NOT NULL | 사용자 그룹 FK |
| user_id | bigint | NOT NULL | 수강생 FK |
| coach_id | bigint | NOT NULL | 코치 FK |
| comment | text | NOT NULL | 코멘트 |
| status | varchar(30) | NOT NULL | 상태 |

### public.trainee_counsel (TraineeCounsel)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| service_type | varchar(30) | NOT NULL | 서비스 타입 |
| user_group_id | bigint | NOT NULL | 사용자 그룹 FK |
| user_id | bigint | NOT NULL | 수강생 FK |
| requested_at | timestamptz | NOT NULL | 요청 일시 |
| content | text | NOT NULL | 상담 내용 |
| response | text | nullable | 응답 |
| responded_at | timestamptz | nullable | 응답 일시 |
| responded_by | bigint | nullable | 응답자 FK |
| trainee_emotion | varchar(50) | nullable | 수강생 감정 |
| counsel_status | varchar(30) | default: PENDING | 상담 상태 |


---

## A.3 orderx 스키마 엔티티 상세

### orderx.order (Order)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | 주문 ID |
| order_pk | varchar | UNIQUE, NOT NULL | 주문 고유키 |
| total_price | decimal(10,2) | NOT NULL | 총 금액 |
| status | varchar(50) | NOT NULL | 주문 상태 (OrderStatus) |
| custom_data | jsonb | nullable, default: {} | 커스텀 데이터 |
| created_at | timestamptz | CreateDateColumn | |
| modified_at | timestamptz | UpdateDateColumn | |
| paid_at | timestamptz | nullable | 결제 일시 |
| cancelled_at | timestamptz | nullable | 취소 일시 |
| failed_at | timestamptz | nullable | 실패 일시 |
| redirect_url | varchar(255) | nullable | 리다이렉트 URL |

관계: OrderMember ← @OneToOne(cascade), OrderItem[] ← @OneToMany(cascade), OrderTransaction[] ← @OneToMany, OrderCouponDiscount[] ← @OneToMany(cascade)

### orderx.order_item (OrderItem)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| order_id | varchar | NOT NULL | 주문 FK |
| product_id | varchar | nullable | 상품 ID |
| originalPrice | decimal(10,2) | NOT NULL | 원가 |
| salePrice | decimal(10,2) | NOT NULL | 판매가 |
| final_price | decimal(10,2) | nullable | 최종가 |
| quantity | int | NOT NULL | 수량 |
| product_details | json | NOT NULL | 상품 상세 |
| expiration_date | timestamptz | nullable | 만료일 |

관계: Order → @ManyToOne

### orderx.order_member (OrderMember)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| order_id | varchar | NOT NULL | 주문 FK |
| member_id | varchar | NOT NULL | 회원 ID |
| member_name | varchar(255) | NOT NULL | 회원 이름 |
| email | varchar(255) | NOT NULL | 이메일 |
| phone | varchar(20) | NOT NULL | 전화번호 |

관계: Order → @OneToOne

### orderx.order_transaction (OrderTransaction)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| order_id | varchar | NOT NULL | 주문 FK |
| merchant_order_id | varchar | NOT NULL | 가맹점 주문 ID |
| transaction_id | varchar | NOT NULL | 트랜잭션 ID |
| amount | decimal(10,2) | NOT NULL | 결제 금액 |
| transaction_status | varchar(50) | NOT NULL | 상태 |
| payment_method | varchar | nullable | 결제 수단 (PaymentMethod) |
| pg_provider | varchar | nullable | PG사 (PgProvider) |
| payment_provider | varchar | NOT NULL | 결제 제공자 (PaymentProvider) |

관계: Order → @ManyToOne

### orderx.order_coupon_discount (OrderCouponDiscount)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| coupon_member_id | int8 | NOT NULL | 쿠폰회원 FK |
| order_id | int8 | NOT NULL | 주문 FK |
| order_item_id | int8 | NOT NULL | 주문항목 FK |
| discount_amount | decimal(15,2) | NOT NULL | 할인 금액 |

### orderx.cart (Cart)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |

관계: CartItem[] ← @OneToMany

### orderx.cart_item (CartItem)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| cart_id | int8 | NOT NULL | 장바구니 FK |
| product_id | varchar | NOT NULL | 상품 ID |
| original_price | decimal(15,2) | NOT NULL | 원가 |
| sale_price | decimal(15,2) | NOT NULL | 판매가 |
| quantity | integer | NOT NULL | 수량 |
| product_details | jsonb | NOT NULL, default: {} | 상품 상세 |
| expiration_date | timestamptz | nullable | 만료일 |
| deleted_at | timestamptz | nullable | 삭제일 |
| is_purchased | boolean | NOT NULL, default: false | 구매 완료 |
| purchased_at | timestamptz | nullable | 구매 일시 |

관계: Cart → @ManyToOne

### orderx.coupon (Coupon)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| uuid | varchar(36) | UNIQUE, NOT NULL | 쿠폰 UUID |
| name | varchar(50) | NOT NULL | 쿠폰명 |
| description | varchar(255) | NOT NULL | 설명 |
| discount_scope | varchar(50) | NOT NULL | 할인 범위 (ORDER/ITEM) |
| discount_type | varchar(50) | NOT NULL | 할인 유형 (FIXED/PERCENT) |
| discount_value | bigint | NOT NULL | 할인 값 |
| max_discount_amount | bigint | NOT NULL | 최대 할인 금액 |
| min_order_amount | bigint | nullable | 최소 주문 금액 |
| valid_type | varchar(50) | NOT NULL | 유효 유형 |
| valid_from | timestamptz | nullable | 유효 시작 |
| valid_to | timestamptz | nullable | 유효 종료 |
| valid_days | bigint | nullable | 유효 일수 |
| total_quantity | bigint | nullable | 총 수량 |
| status | varchar(50) | NOT NULL | 상태 (ACTIVE/INACTIVE/EXPIRED) |
| restriction_rule | jsonb | NOT NULL | 제한 규칙 |

### orderx.coupon_member (CouponMember)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| uuid | varchar | UNIQUE, NOT NULL | 쿠폰회원 UUID |
| member_id | int | NOT NULL | 회원 ID |
| coupon_id | int | NOT NULL | 쿠폰 FK |
| valid_from | timestamptz | NOT NULL | 유효 시작 |
| valid_to | timestamptz | NOT NULL | 유효 종료 |
| status | varchar(50) | NOT NULL | 상태 |
| issued_at | timestamptz | NOT NULL | 발급일 |
| used_at | timestamptz | nullable | 사용일 |

관계: Coupon → @ManyToOne

### orderx.coupon_member_history (CouponMemberHistory)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| coupon_member_id | bigint | NOT NULL | 쿠폰회원 FK |
| event_type | varchar(50) | NOT NULL | 이벤트 유형 (USE/CANCEL/ISSUE) |
| extra | jsonb | nullable | 추가 데이터 |

### orderx.webhook_history (WebhookHistory)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| origin | varchar | NOT NULL | 웹훅 출처 |
| payload | jsonb | NOT NULL | 페이로드 |


---

## A.4 resource 스키마 엔티티 상세

### resource.instances (Instance)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| name | varchar(100) | NOT NULL | 인스턴스명 |
| provider | enum(CloudProvider) | NOT NULL | 클라우드 제공자 |
| instanceId | varchar(100) | NOT NULL | 인스턴스 ID |
| status | varchar(100) | NOT NULL | 상태 |
| metadata | jsonb | nullable | 메타데이터 |
| region | varchar(100) | NOT NULL | 리전 |
| selfLink | varchar(200) | nullable | 자체 링크 |

관계: InstanceTemplate → @ManyToOne, InstanceGroup → @ManyToOne, Disk[] ← @OneToMany

### resource.instance_templates (InstanceTemplate)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| name | varchar(100) | NOT NULL | 템플릿명 |
| provider | varchar(100) | NOT NULL | 제공자 |
| templateId | varchar(100) | NOT NULL | 템플릿 ID |
| nickname | varchar(100) | nullable | 별명 |
| configuration | jsonb | default: {} | 설정 (machineType, diskSizeGb 등) |
| region | varchar(100) | NOT NULL | 리전 |

관계: Instance[] ← @OneToMany

### resource.instance_groups (InstanceGroup)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| name | varchar(100) | NOT NULL | 그룹명 |
| provider | enum(CloudProvider) | NOT NULL | 제공자 |
| groupId | varchar(100) | NOT NULL | 그룹 ID |
| region | varchar(100) | NOT NULL | 리전 |
| autoScalingMode | enum(AutoScalingMode) | default: OFF | 오토스케일링 |
| targetSize | int | NOT NULL | 목표 크기 |
| currentSize | int | default: 0 | 현재 크기 |
| autoScalingPolicy | jsonb | nullable | 오토스케일링 정책 |

관계: Instance[] ← @OneToMany

### resource.disks (Disk)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| name | varchar(100) | NOT NULL | 디스크명 |
| provider | enum(CloudProvider) | NOT NULL | 제공자 |
| diskPk | varchar(100) | NOT NULL | 디스크 PK |
| type | varchar | NOT NULL | 디스크 타입 |
| status | varchar | NOT NULL | 상태 |
| sizeGb | int | NOT NULL | 크기(GB) |
| region | varchar(100) | NOT NULL | 리전 |
| metadata | jsonb | nullable | 메타데이터 |

관계: Instance → @ManyToOne

### resource.gcp_operations (GcpOperation)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| operationId | varchar(255) | NOT NULL | 오퍼레이션 ID |
| type | enum(GcpOperationType) | NOT NULL | 유형 (CREATE/DELETE/START/STOP) |
| status | varchar(255) | NOT NULL | 상태 |
| resourceName | varchar(255) | NOT NULL | 리소스명 |
| metadata | jsonb | nullable | |
| errorMessage | text | nullable | 에러 메시지 |
| startedAt | timestamp | nullable | 시작 시각 |
| completedAt | timestamp | nullable | 완료 시각 |

### resource.jupyter_hub (JupyterHub)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(100) | NOT NULL | 허브 이름 |
| url | varchar(500) | NOT NULL | 허브 URL |
| api_token | varchar(500) | NOT NULL | API 토큰 |
| max_users | int | default: 100 | 최대 사용자 |
| is_active | boolean | default: true | 활성화 |

관계: JupyterUser[] ← @OneToMany, JupyterHubApiLog[] ← @OneToMany

### resource.jupyter_user (JupyterUser)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | UNIQUE, NOT NULL | 회원 ID |
| hub_id | int | NOT NULL | 허브 FK |
| username | varchar(100) | NOT NULL | 사용자명 |
| is_admin | boolean | default: false | 관리자 여부 |
| is_active | boolean | default: true | 활성화 |
| is_migrated | boolean | default: false | 마이그레이션 완료 |

관계: JupyterHub → @ManyToOne, JupyterServer[] ← @OneToMany, JupyterUserToken[] ← @OneToMany

### resource.jupyter_server (JupyterServer)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |
| server_name | varchar(100) | default: '' | 서버명 |
| url | varchar(500) | nullable | URL |
| started_at | timestamptz | nullable | 시작 시간 |
| stop_requested_at | timestamptz | nullable | 정지 요청 |
| stop_completed_at | timestamptz | nullable | 정지 완료 |
| deletion_verified_at | timestamptz | nullable | 삭제 확인 |
| is_active | boolean | default: true | 활성화 |
| metadata | jsonb | nullable | |
| server_response_metadata | jsonb | nullable | 응답 메타 |

관계: JupyterUser → @ManyToOne

### resource.jupyter_user_token (JupyterUserToken)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |
| token | varchar(500) | UNIQUE, NOT NULL | API 토큰 |
| name | varchar(100) | nullable | 토큰명 |
| expires_at | timestamptz | nullable | 만료 시간 |
| is_active | boolean | default: true | 활성화 |

### resource.jupyter_hub_api_log (JupyterHubApiLog)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| jupyter_hub_id | int8 | NOT NULL | 허브 FK |
| method | varchar(10) | NOT NULL | HTTP 메서드 |
| url | text | NOT NULL | 요청 URL |
| request_headers | jsonb | nullable | 요청 헤더 |
| request_body | jsonb | nullable | 요청 본문 |
| request_at | timestamptz | nullable | 요청 시각 |
| status_code | int | nullable | 응답 상태 |
| response_body | jsonb | nullable | 응답 본문 |
| response_time_ms | int | nullable | 응답 시간(ms) |

### resource.jupyter_server_event_log (JupyterServerEventLog)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| userUuid | varchar(36) | NOT NULL | 사용자 UUID |
| serverName | varchar(100) | NOT NULL | 서버명 |
| podName | varchar(255) | NOT NULL | Pod명 |
| type | varchar(50) | NOT NULL | 이벤트 유형 |
| reason | varchar(255) | NOT NULL | 이유 |
| message | text | NOT NULL | 메시지 |
| eventAt | timestamptz | NOT NULL | 이벤트 시각 |
| eventPayload | jsonb | NOT NULL | 페이로드 |

### resource.user_resources (UserResource)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | nullable | 회원 ID |
| accessUrl | varchar(255) | nullable | 접근 URL |
| metadata | jsonb | nullable | |
| type | varchar(255) | NOT NULL | 리소스 유형 |
| status | enum(UserResourceStatus) | default: RUNNING | 상태 |
| stop_requested_at | timestamptz | nullable | 정지 요청 |
| stop_processed_at | timestamptz | nullable | 정지 처리 |
| stop_completed_at | timestamptz | nullable | 정지 완료 |
| last_accessed_at | timestamptz | nullable | 마지막 접근 |

### resource.user_instances (UserInstance)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| userId | varchar(100) | NOT NULL | 사용자 ID |
| instanceId | int | NOT NULL | 인스턴스 FK |
| member_id | int8 | nullable | 회원 ID |
| accessUrl | varchar(255) | nullable | 접근 URL |
| metadata | jsonb | nullable | |

### resource.user_disks (UserDisk)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| userId | varchar(100) | NOT NULL | 사용자 ID |
| metadata | jsonb | nullable | |

관계: Disk → @ManyToOne

### resource.user_resource_logs (UserResourceLog)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| user_resource_id | int8 | nullable | 리소스 FK |
| member_id | int8 | NOT NULL | 회원 ID |
| action | varchar(50) | NOT NULL | 액션 (CREATE/UPDATE/DELETE/START/STOP) |
| status | varchar(50) | NOT NULL | 상태 (SUCCESS/FAILED/PENDING) |
| message | text | nullable | 메시지 |
| metadata | jsonb | nullable | |
| ipAddress | varchar(45) | nullable | IP |
| userAgent | varchar(500) | nullable | User Agent |

### resource.resource_profiles (ResourceProfile)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| slug | varchar(50) | UNIQUE, NOT NULL | 슬러그 |
| name | varchar(100) | NOT NULL | 이름 |
| description | text | nullable | 설명 |
| machineType | varchar(50) | NOT NULL | 머신 타입 |
| pricePerHour | decimal(10,6) | NOT NULL | 시간당 가격 |
| resourceType | varchar(20) | NOT NULL | cpu/gpu 등 |
| vcpu | decimal(3,1) | NOT NULL | vCPU |
| memoryGb | int | NOT NULL | 메모리(GB) |
| gpuCount | int | nullable | GPU 수 |
| gpuType | varchar(50) | nullable | GPU 유형 |
| isActive | boolean | default: true | 활성화 |
| isSpot | boolean | default: false | 스팟 여부 |
| sortOrder | int | default: 0 | 정렬 |

### resource.lms_user_report (LmsUserReport)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 회원 ID |
| course_id | int8 | NOT NULL | 강좌 ID |
| node_version_id | int8 | NOT NULL | 노드 버전 ID |
| step_id | int8 | NOT NULL | 단계 ID |
| localschool_id | int8 | NOT NULL | 지역학교 ID |
| errorMessage | text | nullable | 에러 메시지 |
| kernelStatus | varchar(50) | nullable | 커널 상태 |
| instanceStatus | varchar(50) | nullable | 인스턴스 상태 |

---

## A.5 class 스키마 엔티티 상세

### class.class (Class)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| title | varchar(255) | NOT NULL | 클래스 제목 |
| handle | varchar(255) | UNIQUE | SEO URL slug |
| description | text | nullable | 설명 |
| bodyHtml | text | nullable | 상세 HTML |
| status | enum(ClassStatus) | default: DRAFT | 상태 |
| price | decimal(10,2) | NOT NULL | 가격 |
| compareAtPrice | decimal(10,2) | nullable | 할인 전 가격 |
| images | jsonb | nullable | 이미지 URL 배열 |
| seoMetadata | jsonb | nullable | SEO 메타 |
| published | boolean | default: true | 발행 여부 |
| publishedAt | timestamp | nullable | 발행 일시 |
| viewCount | int | default: 0 | 조회수 |
| orderCount | int | default: 0 | 주문수 |
| likeCount | int | default: 0 | 좋아요수 |
| metadata | jsonb | nullable | 확장 메타 |
| orderable | boolean | default: false | 주문 가능 |
| course_id | int8 | nullable | 과정 FK |

관계: ClassClassCategoryMapping[] ← @OneToMany, ClassClassTagMapping[] ← @OneToMany, ClassClassCollectionMapping[] ← @OneToMany, ClassClassAttributeMapping[] ← @OneToMany, ClassCreatorMapping[] ← @OneToMany

### class.class_category (ClassCategory) — Tree Entity
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 카테고리명 |
| handle | varchar(255) | UNIQUE | 핸들 |
| description | text | nullable | 설명 |
| parent_id | bigint | nullable | 부모 카테고리 FK (자기참조) |
| sortOrder | int | default: 0 | 정렬 |
| isVisible | boolean | default: true | 노출 여부 |

### class.class_tag (ClassTag)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 태그명 |
| handle | varchar(255) | UNIQUE | 핸들 |
| tag_type | varchar | NOT NULL | 태그 타입 |
| color | varchar | nullable | 헥스 컬러 |
| is_visible | boolean | default: true | 노출 |
| sort_order | int | default: 0 | 정렬 |
| metadata | jsonb | nullable | 메타 |

### class.class_collection (ClassCollection)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| title | varchar(255) | NOT NULL | 컬렉션명 |
| handle | varchar(255) | UNIQUE | 핸들 |
| description | text | nullable | 설명 |
| collection_type | varchar | NOT NULL | 컬렉션 유형 |
| rules | jsonb | nullable | 스마트 컬렉션 규칙 |
| published | boolean | default: true | 발행 |
| sortOrder | int | default: 0 | 정렬 |
| metadata | jsonb | nullable | 메타 |

### class.class_attribute (ClassAttribute)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 속성명 |
| handle | varchar(255) | UNIQUE | 핸들 |
| value_type | enum(ValueType) | default: STRING | 값 타입 |
| is_required | boolean | default: false | 필수 여부 |
| is_filterable | boolean | default: true | 필터 가능 |
| is_searchable | boolean | default: true | 검색 가능 |
| default_value | jsonb | nullable | 기본값 |
| options | jsonb | nullable | 선택 옵션 |

### class.class_attribute_value (ClassClassAttributeMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| class_id | bigint | NOT NULL | 클래스 FK |
| attribute_id | bigint | NOT NULL | 속성 FK |
| value | jsonb | NOT NULL | 속성값 |

### class.class_category_mapping / class_tag_mapping / class_collection_mapping / class_creator_mapping
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| class_id | bigint | NOT NULL | 클래스 FK |
| {category/tag/collection/creator}_id | bigint | NOT NULL | 대상 FK |

### class.class_creator (ClassCreator)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int | PK, auto-increment | |
| name | varchar | NOT NULL | 크리에이터명 |
| handle | varchar | UNIQUE | 핸들 |
| email | varchar | nullable, UNIQUE | 이메일 |
| bio | text | nullable | 소개 |
| bodyHtml | text | nullable | 상세 HTML |
| specialties | jsonb | nullable | 전문 분야 |
| experienceYears | int | default: 0 | 경력 연수 |
| socialLinks | jsonb | nullable | 소셜 링크 |
| status | varchar | default: ACTIVE | 상태 |
| rating | decimal(3,2) | default: 0 | 평점 |

### class.class_review (ClassReview)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| class_id | bigint | NOT NULL, UNIQUE(member_id) | 클래스 FK |
| member_id | bigint | NOT NULL, UNIQUE(class_id) | 회원 FK |
| rating | decimal(2,1) | NOT NULL | 평점 (1.0~5.0) |
| content | text | NOT NULL | 리뷰 내용 |
| status | enum(ReviewStatus) | default: ACTIVE | 상태 |
| admin_note | text | nullable | 관리자 메모 |
| deleted_at | timestamp | nullable | 삭제일 |

### class.class_order_enrol (ClassOrderEnrol)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | bigint | NOT NULL | 회원 ID |
| class_id | bigint | nullable | 클래스 FK |
| course_id | bigint | NOT NULL | 과정 FK |
| round_schedule_id | bigint | nullable | 회차 스케줄 FK |
| user_enrolments_id | bigint | nullable | 수강등록 FK |
| order_pk | varchar | NOT NULL | 주문 PK |
| status | varchar | NOT NULL | 상태 |
| status_reason | varchar | nullable | 상태 사유 |

### class.class_order_request_group (ClassOrderRequestGroup)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| code | varchar | UNIQUE, NOT NULL | 그룹 코드 |
| name | varchar | NOT NULL | 그룹명 |
| description | text | nullable | 설명 |
| displayable | boolean | default: false | 노출 여부 |
| orderable | boolean | default: false | 주문 가능 |

### class.class_training_course_template (ClassTrainingCourseTemplate)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| class_id | int8 | NOT NULL | 클래스 FK |
| template | text | NOT NULL | 템플릿 내용 |

관계: Class → @OneToOne (onDelete: CASCADE)

---

## A.6 membership 스키마 엔티티 상세

### membership.auth_member (AuthMember)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK, auto-increment | |
| created_at | timestamptz | NOT NULL | 생성일 |
| uuid | varchar(255) | UNIQUE | UUID |
| email | varchar(255) | UNIQUE | 이메일 |
| account_status | varchar | NOT NULL | 계정 상태 (ACTIVE/INACTIVE/SUSPENDED/DELETED) |
| is_email_verified | boolean | NOT NULL | 이메일 인증 |
| password_hash | varchar | NOT NULL | 비밀번호 해시 |
| password_updated_at | timestamptz | NOT NULL | 비밀번호 수정일 |

관계: AuthMemberProfile ← @OneToOne, AuthMemberPrivacy ← @OneToOne, AuthMemberLoginHistory[] ← @OneToMany, AuthMemberLoginMethod[] ← @OneToMany, AuthMemberReferral[] ← @OneToMany

### membership.auth_member_profile (AuthMemberProfile)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| nickname | varchar(255) | NOT NULL | 닉네임 |
| organization | varchar(255) | NOT NULL | 소속 |
| job | varchar(255) | NOT NULL | 직업 |
| intro | text | NOT NULL | 자기소개 |
| slack_email | varchar(255) | NOT NULL | 슬랙 이메일 |
| profile_image_url | varchar(500) | NOT NULL | 프로필 이미지 |
| member_id | bigint | NOT NULL | 회원 FK |

### membership.auth_member_privacy (AuthMemberPrivacy)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| username | varchar(255) | NOT NULL | 실명 |
| phone_number | varchar(20) | NOT NULL | 전화번호 |
| birth | date | nullable | 생년월일 |
| gender | char(1) | NOT NULL | 성별 (M/F) |
| address | varchar(255) | NOT NULL | 주소 |
| address_detail | varchar(255) | NOT NULL | 상세 주소 |
| zone_code | varchar(10) | NOT NULL | 우편번호 |
| is_phone_num_verified | boolean | NOT NULL | 전화 인증 |
| mkt_agreement | boolean | NOT NULL | 마케팅 동의 |
| term_agreement | boolean | NOT NULL | 이용약관 동의 |
| unique_key | varchar(255) | NOT NULL | 본인인증 키 |
| member_id | bigint | NOT NULL | 회원 FK |

### membership.auth_member_login_history (AuthMemberLoginHistory)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| ip_address | varchar(50) | NOT NULL | IP |
| full_user_agent | varchar(2000) | NOT NULL | UA |
| login_type | varchar(50) | NOT NULL | 로그인 유형 (EMAIL_PW, SOCIAL_KAKAO 등) |
| login_at | timestamptz | nullable | 로그인 시각 |
| is_logged_out | boolean | NOT NULL | 로그아웃 여부 |
| logout_at | timestamptz | nullable | 로그아웃 시각 |
| member_id | bigint | NOT NULL | 회원 FK |

### membership.auth_member_login_method (AuthMemberLoginMethod)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| login_type | varchar | NOT NULL | 로그인 유형 |
| provider_uuid | varchar | NOT NULL | 소셜 프로바이더 UUID |
| additional_info | jsonb | nullable | 추가 정보 |
| member_id | bigint | NOT NULL | 회원 FK |

### membership.auth_member_referral (AuthMemberReferral)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | bigint | PK | |
| member_id | bigint | NOT NULL | 회원 FK |
| referral_type | varchar(30) | NOT NULL | 유입 유형 |
| referral_service_code | varchar(255) | nullable | 유입 서비스 코드 |
| referral_url | text | nullable | 유입 URL |

### membership.auth_member_settlement_info (MemberSettlementInfo)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | bigint | NOT NULL | 회원 ID |
| type | varchar(30) | NOT NULL | 정산 유형 (개인/법인) |
| registration_number | varchar(100) | NOT NULL | 주민/사업자번호 |
| bank_code | varchar(30) | NOT NULL | 은행 코드 |
| account_holder | varchar(100) | NOT NULL | 예금주 |
| account_number | varchar(100) | NOT NULL | 계좌번호 |
| address | varchar(255) | NOT NULL | 주소 |
| encryption_key_version | varchar(20) | NOT NULL | 암호화 키 버전 |

### membership.member_group (MemberGroup)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| type | varchar(100) | NOT NULL | 그룹 타입 |
| name | varchar(100) | UNIQUE, NOT NULL | 그룹명 |
| description | varchar(255) | NOT NULL | 설명 |
| course_semester_id | bigint | nullable | 과정 학기 FK |

### membership.member_group_mapping (MemberGroupMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | bigint | NOT NULL | 회원 FK |
| group_id | bigint | NOT NULL | 그룹 FK |
| role | varchar(100) | NOT NULL | 역할 |
| enrolment_status | varchar(100) | default: IN_PROGRESS | 등록 상태 |

### membership.push_notification (PushNotification)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | bigint | NOT NULL | 회원 ID |
| notification_service_id | varchar | NOT NULL | 알림 서비스 FK |
| title | text | NOT NULL | 제목 |
| body | text | NOT NULL | 본문 |
| link | text | nullable | 링크 |
| sent_at | timestamptz | NOT NULL | 발송 일시 |
| is_read | boolean | default: false | 읽음 |
| is_clicked | boolean | default: false | 클릭 |
| is_deleted | boolean | default: false | 삭제 |
| ref_id | bigint | nullable | 참조 ID |

### membership.notification_service (NotificationService)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| code | varchar(50) | UNIQUE, NOT NULL | 서비스 코드 |
| name | varchar(100) | NOT NULL | 서비스 이름 |
| icon | varchar(255) | NOT NULL | 아이콘 URL |

### membership.web_push_token (WebPushToken)
*extends ModulabsUUIDBaseEntity*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| memberId | bigint | nullable | 회원 ID |
| service | varchar(30) | NOT NULL | 서비스 |
| pushToken | varchar(255) | NOT NULL | 푸시 토큰 |
| userAgent | varchar(500) | NOT NULL | UA |

---

## A.7 biz 스키마 엔티티 상세

### biz.companies (Company)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 기업명 |
| aliases | jsonb | nullable | 기업 별칭 |
| type | varchar(50) | NOT NULL | 기업 유형 |
| address | varchar(500) | nullable | 주소 |
| notes | text | nullable | 비고 |

관계: ClientContact[] ← @OneToMany, Inquiry[] ← @OneToMany, SalesProposal[] ← @OneToMany, Project[] ← @OneToMany

### biz.inquiries (Inquiry)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| company_id | int8 | nullable | 기업 FK |
| inquiry_type | varchar(100) | nullable | 문의 유형 |
| inquiry_content | jsonb | nullable | 문의 내용 |
| inquiry_date | date | nullable | 문의일 |
| status | varchar(50) | NOT NULL, default: 접수 | 상태 |
| source_channel ~ source_content | varchar | nullable | UTM 파라미터 |
| ga_client_id / ga_session_id | varchar(100) | nullable | GA4 연동 |

### biz.sales_proposals (SalesProposal)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| company_id | int8 | NOT NULL | 기업 FK |
| inquiry_id | int8 | nullable | 문의 FK |
| proposal_number | varchar(50) | UNIQUE, NOT NULL | 제안 번호 |
| proposed_name | varchar(500) | NOT NULL | 제안명 |
| status | varchar(50) | NOT NULL | 상태 |
| budget | decimal(15,2) | nullable | 예산 |
| sales_stage | varchar(50) | NOT NULL | 영업 단계 |

관계: Company → @ManyToOne, Inquiry → @ManyToOne, Project[] ← @OneToMany, ProposalAssignee[] ← @OneToMany

### biz.projects (Project)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| company_id | int8 | NOT NULL | 기업 FK |
| sales_proposal_id | int8 | nullable | 제안 FK |
| project_name | varchar(500) | NOT NULL | 프로젝트명 |
| contract_amount | decimal(15,2) | NOT NULL | 계약 금액 |
| start_date | date | nullable | 시작일 |
| end_date | date | nullable | 종료일 |
| status | varchar(50) | NOT NULL | 상태 |

관계: EducationSession[] ← @OneToMany, ProjectAssignee[] ← @OneToMany

### biz.education_sessions (EducationSession)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| project_id | int8 | NOT NULL | 프로젝트 FK |
| round | int | NOT NULL | 회차 |
| session_number | int | NOT NULL | 세션 번호 |
| session_date | date | nullable | 세션 날짜 |
| session_hours | decimal(3,1) | nullable | 세션 시간 |
| format | varchar(50) | NOT NULL | 형식 |
| satisfaction_score | decimal(3,1) | nullable | 만족도 |

### biz.instructors (Instructor)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | NOT NULL | 강사명 |
| email | varchar(255) | nullable | 이메일 |
| instructor_level | varchar(50) | nullable | 강사 등급 |
| specialization | varchar(500) | nullable | 전문 분야 |
| hourly_rate | decimal(15,2) | NOT NULL | 시간당 단가 |

### biz.client_contacts (ClientContact)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| company_id | int8 | NOT NULL | 기업 FK |
| name | varchar(255) | NOT NULL | 담당자명 |
| position | varchar(100) | nullable | 직책 |
| email | varchar(255) | nullable | 이메일 |
| phone | varchar(50) | nullable | 전화 |
| department | varchar(255) | nullable | 부서 |

### biz.training_topic (TrainingTopic)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| name | varchar(255) | UNIQUE, NOT NULL | 주제명 |
| is_visible | boolean | NOT NULL | 노출 여부 |
| display_order | int | NOT NULL, default: 0 | 정렬 |

---

## A.8 channeltalk 스키마 엔티티 상세

> 모두 `extends ModulabsBaseModel` (id int8 PK, createdAt, modifiedAt)

### channeltalk.channeltalk_conversation (ChanneltalkConversation)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| external_chat_id | bigint | nullable | 외부 대화 ID |
| chat_type | varchar(16) | nullable | 대화 유형 |
| priority | varchar(16) | nullable | 우선순위 |
| state | varchar(16) | nullable | 상태 |
| opened_at | timestamptz | nullable | 오픈 시각 |
| closed_at | timestamptz | nullable | 마감 시각 |
| member_id | bigint | nullable | 회원 ID |

### channeltalk.channeltalk_timeline_item (ChanneltalkTimelineItem)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| channeltalk_conversation_id | bigint | NOT NULL | 대화 FK |
| item_type | varchar(16) | nullable | 항목 유형 |
| occurred_at | timestamptz | NOT NULL | 발생 시각 |
| direction | varchar(16) | nullable | 방향 |

### channeltalk.channeltalk_message_block (ChanneltalkMessageBlock)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| channeltalk_timeline_item_id | bigint | NOT NULL | 타임라인 FK |
| seq | int | NOT NULL | 순서 |
| block_type | varchar(16) | nullable | 블록 유형 |
| text | text | nullable | 텍스트 |
| data | jsonb | nullable | 데이터 |

### channeltalk.channeltalk_guest / channeltalk_manager / channeltalk_bot / channeltalk_tag / channeltalk_file_asset / channeltalk_conversation_participant / channeltalk_conversation_tag / channeltalk_event_detail / raw_data
> 각각 채널톡 연동 데이터 저장. 상세는 본문 섹션 11 참조.

---

## A.9 section 스키마 엔티티 상세

### section.section_page (SectionPage)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| page_key | varchar(100) | NOT NULL, UNIQUE(version) | 페이지 키 |
| version | varchar(50) | NOT NULL, UNIQUE(page_key) | 버전 |
| description | text | nullable | 설명 |
| status | enum(SectionPageStatus) | default: draft | 상태 (published/draft/archived) |

관계: SectionMapping[] ← @OneToMany

### section.section_definition (SectionDefinition)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| type | varchar(100) | NOT NULL | 섹션 유형 |
| default_meta_value | jsonb | nullable | 기본 메타 |

관계: Section[] ← @OneToMany

### section.section (Section)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| meta_value | jsonb | NOT NULL | 메타 데이터 |
| status | enum(SectionStatus) | default: active | 상태 |
| section_definition_id | bigint | NOT NULL | 정의 FK |

### section.section_mapping (SectionMapping)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| section_id | bigint | NOT NULL | 섹션 FK |
| section_page_id | bigint | NOT NULL | 섹션 페이지 FK |
| sort_order | int | default: 0 | 정렬 |

---

## A.10 vod 스키마 엔티티 상세 (vod DB 커넥션)

### vod.service (VodServiceEntity)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| name | varchar(50) | NOT NULL | 서비스명 |
| s3Region | varchar(30) | NOT NULL | S3 리전 |
| s3Bucket | varchar(50) | NOT NULL | S3 버킷 |
| expiresIn | int | default: 3600 | 만료 시간(초) |
| useCdn | boolean | default: false | CDN 사용 |
| cdnHost | varchar(300) | NOT NULL | CDN 호스트 |

관계: VodFolder[] ← @OneToMany, VodVideo[] ← @OneToMany

### vod.folder (VodFolder)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| serviceId | int | NOT NULL | 서비스 FK |
| name | varchar(50) | NOT NULL | 폴더명 |
| order | smallint | NOT NULL | 정렬 |
| parentFolderId | int | nullable | 부모 폴더 FK (자기참조) |

관계: VodServiceEntity → @ManyToOne, VodFolder → @ManyToOne(부모), VodVideo[] ← @OneToMany

### vod.video (VodVideo)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| serviceId | int | NOT NULL | 서비스 FK |
| folderId | int | nullable | 폴더 FK |
| title | varchar(100) | NOT NULL | 영상 제목 |
| bucketPath | varchar(300) | NOT NULL | 버킷 경로 |
| isPublic | boolean | default: false | 공개 여부 |
| isDeleted | boolean | default: false | 삭제 여부 |
| viewCount | int8 | default: 0 | 조회수 |
| masterVideoFileVersion | int8 | default: 1 | 마스터 파일 버전 |

관계: VodVideoFile[] ← @OneToMany

### vod.video_file (VodVideoFile)
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| id | int8 | PK, auto-increment | |
| videoId | int | NOT NULL | 비디오 FK |
| version | int | NOT NULL | 버전 |
| width | int | NOT NULL | 너비 |
| height | int | NOT NULL | 높이 |
| hlsFile | varchar(300) | NOT NULL | HLS 파일 경로 |
| thumbnailFile | varchar(300) | NOT NULL | 썸네일 경로 |
| originFile | varchar(300) | NOT NULL | 원본 경로 |
| fileSize | int8 | default: 0 | 파일 크기 |
| duration | int | default: 0 | 길이(초) |

---

## A.11 기타 (Lab/Momo) 엔티티 상세

### service.lab_meta (LabMeta)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| chief_id | bigint | NOT NULL | 랩장 ID |
| name | varchar(255) | NOT NULL | 랩 이름 |
| intro | text | NOT NULL | 소개 |
| intro_short | text | NOT NULL | 짧은 소개 |
| is_visible | boolean | NOT NULL | 노출 여부 |
| fields | jsonb | nullable | 연구 분야 |
| expected_results | jsonb | nullable | 예상 결과물 |
| research_method | text | NOT NULL | 연구 방법 |
| research_status | varchar(20) | NOT NULL | 연구 상태 |
| status | varchar(20) | NOT NULL | 랩 상태 |
| total_participants | integer | NOT NULL | 총 참여자 |
| curriculum | jsonb | NOT NULL | 커리큘럼 |
| pre_questions | jsonb | NOT NULL | 사전 질문 |

관계: LabParticipant[] ← @OneToMany, LabApplicant[] ← @OneToMany, LabOperation ← @OneToOne

### service.lab_proposal (LabProposal)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| created_by | int | NOT NULL | 작성자 ID |
| proposalStatus | enum(LabProposalStatus) | default: TEMPORARY_SAVED | 제안 상태 |
| cancel_reason | text | nullable | 취소 사유 |
| proposalStep | enum(LabProposalStep) | default: RESEARCH_PLAN | 제안 단계 |

관계: LabProposalResearchDetail ← @OneToOne, LabProposalOperation ← @OneToOne, LabProposalPersonalStatement ← @OneToOne, LabProposalSetupPreparation ← @OneToOne, LabProposalFeedback[] ← @OneToMany

### service.momo (Momo)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| member_id | int8 | NOT NULL | 개설자 ID |
| name | varchar(100) | NOT NULL | 모임 이름 |
| activity_type | varchar | NOT NULL | 활동 유형 |
| meeting_place | varchar | NOT NULL | 모임 장소 유형 |
| start_date | date | NOT NULL | 시작일 |
| end_date | date | NOT NULL | 종료일 |
| recruit_method | varchar | NOT NULL | 모집 방법 |
| recruit_status | varchar | NOT NULL | 모집 상태 |
| activity_status | varchar | NOT NULL | 활동 상태 |
| payable | boolean | default: false | 유료 여부 |

관계: MomoParticipant[] ← @OneToMany

### service.momo_participant (MomoParticipant)
*extends ModulabsBaseModel*
| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|---------|------|
| momo_id | int8 | NOT NULL | 모모 FK |
| member_id | int8 | NOT NULL | 회원 ID |
| role | varchar | nullable | 역할 |
| status | varchar | NOT NULL | 참여 상태 |
| recruit_method | varchar | NOT NULL | 모집 방법 |
| order_pk | varchar | nullable | 주문 PK |

### (default).momo_settlement (MomoSettlement)
*extends ModulabsUUIDBaseEntity*
> 정산 관련 필드: total_paid_amount, total_supply_amount, total_settlement_amount, total_actual_settlement_amount 등 (decimal 15,2). 상세는 배치 3 결과 참조.

### (default).momo_settlement_record (MomoSettlementRecord)
*extends ModulabsBaseModel*
> 개별 정산 레코드: payee_member_id, sale_price, pg_fee_rate, pg_fee_amount, status 등.

