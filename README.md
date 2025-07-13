# Mertani 강우량 데이터 Supabase 동기화

Mertani API에서 강우량 센서 데이터를 수집하여 Supabase에 자동으로 동기화하는 프로젝트입니다.

## 🌧️ 주요 기능

- **자동 동기화**: GitHub Actions를 통해 매시간 자동 실행
- **다중 센서 지원**: 최대 26개 강우량 센서 동시 처리
- **실시간 데이터**: 최근 1일간의 강우량 데이터 수집
- **배치 처리**: 대용량 데이터의 효율적인 Supabase 저장
- **에러 처리**: 안정적인 오류 처리 및 로깅

## 🚀 설정 방법

### 1. Supabase 설정

1. [Supabase](https://supabase.com)에서 새 프로젝트 생성
2. SQL 에디터에서 `supabase_setup.sql` 실행
3. Settings > API에서 URL과 anon key 확인

### 2. GitHub Secrets 설정

GitHub 저장소의 **Settings > Secrets and variables > Actions**에서 다음 시크릿을 추가:

#### 필수 설정
```
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
MERTANI_USER_EMAIL=your_mertani_email
MERTANI_USER_PASSWORD=your_mertani_password
WEATHER_TABLE_NAME=rainfall_data
```

#### 센서 ID 설정 (최대 26개)
```
MERTANI_RAINFALL_SENSOR_1=sensor_id_1
MERTANI_RAINFALL_SENSOR_2=sensor_id_2
...
MERTANI_RAINFALL_SENSOR_26=sensor_id_26
```

### 3. Mertani 센서 ID 확인

1. [Mertani](https://data.mertani.co.id)에 로그인
2. 센서 관리에서 강우량 센서 ID 확인
3. GitHub Secrets에 센서 ID 등록

## 📊 데이터 구조

### Supabase 테이블 스키마

```sql
rainfall_data (
    id BIGSERIAL PRIMARY KEY,
    sensor_id TEXT NOT NULL,           -- 센서 ID
    sensor_name TEXT,                  -- 센서명
    sensor_unit TEXT DEFAULT 'mm',     -- 단위
    datetime TIMESTAMPTZ,              -- 측정 시간
    value_calibration DECIMAL(10,4),   -- 보정된 값
    value_raw DECIMAL(10,4),           -- 원시 값
    timestamp TIMESTAMPTZ NOT NULL,    -- 동기화 시간
    raw_data JSONB,                    -- 원본 데이터
    created_at TIMESTAMPTZ DEFAULT NOW()
)
```

## ⏰ 실행 스케줄

- **자동 실행**: 매시간 (UTC 기준)
- **수동 실행**: GitHub Actions에서 "Run workflow" 버튼으로 즉시 실행 가능

## 🔧 로컬 테스트

1. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일에 실제 값 입력
```

2. 의존성 설치
```bash
pip install -r requirements.txt
```

3. 실행
```bash
python sync_weather.py
```

## 📈 모니터링

- GitHub Actions 탭에서 실행 로그 확인
- Supabase 대시보드에서 데이터 확인
- 실패 시 GitHub Actions에서 알림

## 🛠️ 기술 스택

- **Python 3.11**
- **Supabase** (PostgreSQL 기반)
- **GitHub Actions** (CI/CD)
- **Mertani API** (강우량 데이터)

## 🔒 보안

- 모든 민감한 정보는 GitHub Secrets로 관리
- Supabase RLS (Row Level Security) 활성화
- API 키와 비밀번호는 환경 변수로 관리

## 📝 로그 예시

```
🌧️ Mertani 강우량 데이터 수집 및 Supabase 동기화 시작
------------------------------------------------------------
🔐 Mertani 로그인 중...
✅ 로그인 성공!

📡 강우량 데이터 수집 중...
📅 데이터 수집 기간: 2024-01-15 10:00:00 ~ 2024-01-16 10:00:00
🌧️ 총 5개 강우량 센서 데이터 수집 시작
📡 센서 1/5: abc12345...
   ✅ 데이터 수집 완료
📡 센서 2/5: def67890...
   ✅ 데이터 수집 완료

💾 Supabase 동기화 중...
배치 1 저장 완료: 150 개의 레코드
총 150개의 레코드가 Supabase에 저장되었습니다.
✅ 동기화 완료!

============================================================
📊 동기화 요약
============================================================
📡 총 센서: 5개
✅ 성공: 5개
❌ 실패: 0개
💾 저장된 레코드: 150개
```

## 🐛 문제 해결

### 일반적인 오류

1. **로그인 실패**: Mertani 계정 정보 확인
2. **센서 데이터 없음**: 센서 ID가 올바른지 확인
3. **Supabase 연결 오류**: URL과 API 키 확인
4. **권한 오류**: Supabase RLS 정책 확인

### 로그 확인

- GitHub Actions > Workflows > Mertani Rainfall Data Sync > Run ID > sync-rainfall-data
- 각 단계별 로그 확인 가능

## 📞 지원

문제가 발생하면 GitHub Issues에 등록해주세요. 