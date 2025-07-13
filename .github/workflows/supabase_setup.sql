-- Mertani 강우량 데이터 Supabase 테이블 스키마
-- 디바이스 정보와 센서 데이터를 함께 저장

-- 기존 테이블이 있다면 삭제
DROP TABLE IF EXISTS rainfall_data CASCADE;

-- 강우량 데이터 테이블 생성
CREATE TABLE rainfall_data (
    id BIGSERIAL PRIMARY KEY,
    
    -- 센서 정보
    sensor_company_id TEXT NOT NULL,
    sensor_name TEXT,
    sensor_unit TEXT DEFAULT 'mm',
    
    -- 디바이스 정보
    device_id TEXT,
    device_name TEXT,
    gps_location_lat DECIMAL(10, 8),
    gps_location_lng DECIMAL(11, 8),
    
    -- 측정 데이터
    datetime TIMESTAMPTZ,
    value_calibration DECIMAL(10, 4),
    value_raw DECIMAL(10, 4),
    
    -- 메타데이터
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX idx_rainfall_sensor_company_id ON rainfall_data(sensor_company_id);
CREATE INDEX idx_rainfall_device_id ON rainfall_data(device_id);
CREATE INDEX idx_rainfall_datetime ON rainfall_data(datetime);
CREATE INDEX idx_rainfall_created_at ON rainfall_data(created_at);

-- 복합 인덱스 (센서별 시간별 조회 최적화)
CREATE INDEX idx_rainfall_sensor_datetime ON rainfall_data(sensor_company_id, datetime);

-- Row Level Security (RLS) 활성화
ALTER TABLE rainfall_data ENABLE ROW LEVEL SECURITY;

-- RLS 정책: 모든 사용자가 읽기/쓰기 가능 (필요시 수정)
CREATE POLICY "Enable read access for all users" ON rainfall_data
    FOR SELECT USING (true);

CREATE POLICY "Enable insert access for all users" ON rainfall_data
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update access for all users" ON rainfall_data
    FOR UPDATE USING (true);



-- 함수: 중복 데이터 방지 (같은 센서, 같은 시간의 데이터가 있으면 업데이트)
CREATE OR REPLACE FUNCTION upsert_rainfall_data()
RETURNS TRIGGER AS $$
BEGIN
    -- 같은 센서, 같은 시간의 데이터가 있으면 업데이트
    UPDATE rainfall_data 
    SET 
        value_calibration = NEW.value_calibration,
        value_raw = NEW.value_raw,
        sensor_name = COALESCE(NEW.sensor_name, rainfall_data.sensor_name),
        device_name = COALESCE(NEW.device_name, rainfall_data.device_name),
        gps_location_lat = COALESCE(NEW.gps_location_lat, rainfall_data.gps_location_lat),
        gps_location_lng = COALESCE(NEW.gps_location_lng, rainfall_data.gps_location_lng),
        raw_data = NEW.raw_data,
        timestamp = NOW()
    WHERE 
        sensor_company_id = NEW.sensor_company_id 
        AND datetime = NEW.datetime;
    
    -- 업데이트된 행이 없으면 새로 삽입
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 트리거 생성
CREATE TRIGGER trigger_upsert_rainfall_data
    BEFORE INSERT ON rainfall_data
    FOR EACH ROW
    EXECUTE FUNCTION upsert_rainfall_data();

-- 테이블 정보 출력
\echo '=== 테이블 생성 완료 ==='
\echo '테이블명: rainfall_data'
\echo '주요 컬럼:'
\echo '  - sensor_company_id: 센서 ID'
\echo '  - device_id/device_name: 디바이스 정보'
\echo '  - gps_location_lat/lng: 위치 정보'
\echo '  - datetime: 측정 시간'
\echo '  - value_calibration: 보정된 강우량 값'
\echo '  - value_raw: 원시 강우량 값'
\echo ''
\echo '특징:'
\echo '  - 중복 데이터 자동 방지 (같은 센서, 같은 시간)'
\echo '  - 성능 최적화 인덱스 포함'
\echo '  - Row Level Security 활성화'
\echo '  - 최소한의 저장 공간 사용' 