import os
import json
import http.client
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import hashlib

# 환경 변수 로드
load_dotenv()

class MertaniRainfallAPI:
    def __init__(self, base_url: str = "https://data.mertani.co.id"):
        self.base_url = base_url
        self.access_token = None
        self.company_id = None
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        # 캐시: 센서 목록과 디바이스 정보
        self._sensors_cache = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5분 캐시
        
        # 중복 데이터 캐시 (센서별 마지막 처리 시간)
        self._last_processed_cache = {}
        self._data_cache = {}  # 센서별 데이터 캐시

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """로그인을 수행하고 토큰을 저장합니다."""
        conn = http.client.HTTPSConnection(self.base_url.replace("https://", ""))
        payload = json.dumps({
            "strategy": "web",
            "email": email,
            "password": password
        })
        try:
            conn.request("POST", "/users/login", payload, self.headers)
            res = conn.getresponse()
            response_data = json.loads(res.read().decode("utf-8"))

            if response_data.get('status') == 'OK':
                data = response_data.get('data', {})
                self.access_token = data.get('accessToken')
                self.user_data = data.get('user', {})
                self.company_id = self.user_data.get('company_id')
                self.headers['Authorization'] = self.access_token
                print(f"✅ 로그인 성공!")
                return response_data
            else:
                raise Exception(f"로그인 실패: {response_data}")
        finally:
            conn.close()

    def get_rainfall_data(self, sensor_company_id: str, start_date: str, end_date: str, use_cache: bool = True) -> Dict[str, Any]:
        """강우량 센서 데이터를 조회합니다. (캐시 지원)"""
        if not self.access_token:
            raise Exception("로그인이 필요합니다.")

        # 캐시 키 생성
        cache_key = f"{sensor_company_id}_{start_date}_{end_date}"
        
        # 캐시 확인
        if use_cache and cache_key in self._data_cache:
            cached_data = self._data_cache[cache_key]
            if cached_data.get('timestamp'):
                cache_age = time.time() - cached_data['timestamp']
                if cache_age < 300:  # 5분 캐시
                    print(f"📋 캐시된 데이터 사용: {sensor_company_id[:8]}...")
                    return cached_data['data']
        
        # API 호출
        conn = http.client.HTTPSConnection(self.base_url.replace("https://", ""))
        params = {
            'sensor_company_id': sensor_company_id,
            'start': start_date,
            'end': end_date
        }
        encoded_params = urllib.parse.urlencode(params)
        url = f"/sensors/records?{encoded_params}"
        try:
            conn.request("GET", url, headers=self.headers)
            res = conn.getresponse()
            response_data = json.loads(res.read().decode("utf-8"))
            if response_data.get('status') == 'OK':
                # 캐시에 저장
                if use_cache:
                    self._data_cache[cache_key] = {
                        'data': response_data,
                        'timestamp': time.time()
                    }
                return response_data
            else:
                raise Exception(f"센서 데이터 조회 실패: {response_data}")
        finally:
            conn.close()

    def get_all_rainfall_sensors_with_device_info(self) -> list:
        """
        회사 내 모든 디바이스의 센서 정보와 디바이스 정보를 함께 반환 (캐시 적용)
        """
        # 캐시 확인
        current_time = time.time()
        if (self._sensors_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < self._cache_duration):
            print("📋 캐시된 센서 목록 사용")
            return self._sensors_cache

        if not self.access_token:
            raise Exception("로그인이 필요합니다.")
        
        print("🔍 센서 목록 새로 조회 중...")
        conn = http.client.HTTPSConnection(self.base_url.replace("https://", ""))
        url = f"/devices?company_id={self.company_id}&limit=50"
        try:
            conn.request("GET", url, headers=self.headers)
            res = conn.getresponse()
            response_data = json.loads(res.read().decode("utf-8"))
            if response_data.get('status') == 'OK':
                sensors = []
                print(f"🔍 API 응답에서 디바이스 정보 확인:")
                for i, device in enumerate(response_data.get('data', {}).get('data', [])):
                    device_info = {
                        "device_id": device.get("device_id"),
                        "device_name": device.get("device_name") or device.get("name") or f"Device_{device.get('device_id', 'Unknown')}",
                        "gps_location_lat": device.get("gps_location_lat") or device.get("device_latitude"),
                        "gps_location_lng": device.get("gps_location_lng") or device.get("device_longitude"),
                    }
                    
                    # 디바이스 정보 디버깅 (처음 2개만)
                    if i < 2:
                        print(f"   디바이스 {i+1}:")
                        print(f"     device_id: {device_info['device_id']}")
                        print(f"     device_name: '{device_info['device_name']}' (타입: {type(device_info['device_name'])})")
                        print(f"     센서 수: {len(device.get('sensor_companies', []))}")
                    
                    for sensor in device.get('sensor_companies', []):
                        sensors.append({
                            "sensor_company_id": sensor.get("sensor_company_id"),
                            **device_info
                        })
                
                # 캐시 업데이트
                self._sensors_cache = sensors
                self._cache_timestamp = current_time
                
                if not sensors:
                    print("⚠️ 디바이스에 등록된 센서가 없습니다.")
                else:
                    print(f"✅ {len(sensors)}개 센서 발견")
                return sensors
            else:
                raise Exception(f"디바이스 목록 조회 실패: {response_data}")
        finally:
            conn.close()

    def fetch_single_sensor_data(self, sensor_info: dict, start_date: str, end_date: str) -> tuple:
        """단일 센서 데이터 수집 (병렬 처리용, 중복 감지)"""
        sensor_id = sensor_info['sensor_company_id']
        device_name = sensor_info.get('device_name')
        device_id = sensor_info.get('device_id')
        
        # 디바이스명이 없으면 디바이스 ID나 기본값 사용
        display_name = device_name or device_id or 'Unknown'
        
        # 중복 데이터 감지
        cache_key = f"{sensor_id}_{start_date}_{end_date}"
        if cache_key in self._last_processed_cache:
            last_time = self._last_processed_cache[cache_key]
            time_diff = time.time() - last_time
            if time_diff < 60:  # 1분 내에 처리된 데이터는 스킵
                print(f"⏭️ 중복 데이터 스킵: {sensor_id[:8]}... ({display_name}) - {time_diff:.0f}초 전 처리됨")
                return sensor_id, None, display_name, True  # 성공으로 처리하되 데이터는 None
        
        try:
            data = self.get_rainfall_data(sensor_id, start_date, end_date)
            
            # 처리 시간 기록
            self._last_processed_cache[cache_key] = time.time()
            
            return sensor_id, data, display_name, True
        except Exception as e:
            print(f"❌ 센서 {sensor_id} ({display_name}) 오류: {e}")
            return sensor_id, None, display_name, False

    def fetch_all_rainfall_data_parallel(self, days: int = 1, max_workers: int = 10) -> Dict[str, Any]:
        """모든 강우량 센서의 데이터를 병렬로 수집합니다."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"📅 데이터 수집 기간: {start_str} ~ {end_str}")
        
        # 센서 목록 가져오기 (캐시 활용)
        sensors_with_device_info = self.get_all_rainfall_sensors_with_device_info()
        print(f"🌧️ 총 {len(sensors_with_device_info)}개 센서 데이터 병렬 수집 시작")
        
        # 디버깅: 센서 정보 확인
        print(f"🔍 센서 정보 샘플:")
        for i, sensor_info in enumerate(sensors_with_device_info[:3]):
            print(f"   센서 {i+1}: {sensor_info.get('sensor_company_id', 'N/A')[:8]}...")
            print(f"     디바이스 ID: {sensor_info.get('device_id', 'N/A')}")
            print(f"     디바이스명: '{sensor_info.get('device_name', 'N/A')}' (타입: {type(sensor_info.get('device_name'))})")
            print(f"     위치: ({sensor_info.get('gps_location_lat', 'N/A')}, {sensor_info.get('gps_location_lng', 'N/A')})")
        if len(sensors_with_device_info) > 3:
            print(f"   ... 외 {len(sensors_with_device_info) - 3}개")
        
        all_data = {}
        success_count = 0
        start_time = time.time()
        
        # GitHub Actions 환경에서는 CPU 코어 수를 고려하여 워커 수 조정
        if os.getenv('GITHUB_ACTIONS'):
            max_workers = min(max_workers, 8)  # GitHub Actions에서 안정적인 워커 수
            print(f"🔧 GitHub Actions 환경 감지, 워커 수: {max_workers}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 모든 센서를 동시에 실행
            future_to_sensor = {
                executor.submit(self.fetch_single_sensor_data, sensor_info, start_str, end_str): sensor_info
                for sensor_info in sensors_with_device_info
            }
            
            # 결과 수집
            for future in as_completed(future_to_sensor):
                sensor_id, data, device_name, success = future.result()
                all_data[sensor_id] = data
                if success:
                    success_count += 1
                    print(f"✅ 센서 {sensor_id[:8]}... ({device_name}) 완료")
                else:
                    print(f"❌ 센서 {sensor_id[:8]}... ({device_name}) 실패")
        
        end_time = time.time()
        print(f"\n📊 병렬 처리 완료:")
        print(f"   총 시간: {end_time - start_time:.1f}초")
        print(f"   성공: {success_count}/{len(sensors_with_device_info)}개")
        print(f"   평균: {(end_time - start_time) / len(sensors_with_device_info):.1f}초/센서")
        print(f"   캐시 히트: {len([k for k, v in self._data_cache.items() if time.time() - v.get('timestamp', 0) < 300])}개")
        print(f"   중복 스킵: {len(self._last_processed_cache)}개")
        
        return all_data

class SupabaseSync:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.table_name = os.getenv('WEATHER_TABLE_NAME', 'rainfall_data')

    def transform_rainfall_data(self, rainfall_data: Dict[str, Any], sensors_with_device_info: List[dict]) -> List[Dict[str, Any]]:
        """강우량 데이터를 Supabase에 맞게 변환 (디바이스 정보 포함)"""
        transformed_records = []
        current_time = datetime.now().isoformat()
        
        # 센서별 디바이스 정보 매핑
        device_info_map = {
            sensor['sensor_company_id']: sensor 
            for sensor in sensors_with_device_info
        }
        
        print(f"🔍 디바이스 정보 매핑 확인:")
        print(f"   총 센서 수: {len(device_info_map)}")
        for sensor_id, device_info in list(device_info_map.items())[:3]:  # 처음 3개만 출력
            print(f"   센서 {sensor_id[:8]}... -> 디바이스: {device_info.get('device_name', 'Unknown')}")
        if len(device_info_map) > 3:
            print(f"   ... 외 {len(device_info_map) - 3}개")
        
        for sensor_id, sensor_data in rainfall_data.items():
            if sensor_data and sensor_data.get('status') == 'OK':
                device_info = device_info_map.get(sensor_id, {})
                records = sensor_data.get('data', {}).get('data', [])
                
                for record in records:
                    sensor_master = record.get('sensor_master', {})
                    sensor_records = record.get('sensor_records', [])
                    
                    for sensor_record in sensor_records:
                        # JSON 직렬화 안전성 검사
                        try:
                            raw_data_json = json.dumps(sensor_record, ensure_ascii=False, default=str)
                        except (TypeError, ValueError) as e:
                            print(f"⚠️ JSON 직렬화 실패, 기본값 사용: {e}")
                            raw_data_json = json.dumps({"error": "JSON serialization failed", "data": str(sensor_record)})
                        
                        # 데이터 타입 안전성 검사
                        def safe_float(value):
                            try:
                                return float(value) if value is not None else None
                            except (ValueError, TypeError):
                                return None
                        
                        transformed_record = {
                            'sensor_company_id': str(sensor_id),
                            'sensor_name': str(sensor_master.get('sensor_name', 'Unknown')),
                            'sensor_unit': str(sensor_master.get('sensor_unit', 'mm')),
                            'device_id': str(device_info.get('device_id')) if device_info.get('device_id') else None,
                            'device_name': str(device_info.get('device_name')) if device_info.get('device_name') else None,
                            'gps_location_lat': safe_float(device_info.get('gps_location_lat')),
                            'gps_location_lng': safe_float(device_info.get('gps_location_lng')),
                            'datetime': sensor_record.get('datetime'),
                            'value_calibration': safe_float(sensor_record.get('value_calibration')),
                            'value_raw': safe_float(sensor_record.get('value_raw')),
                            'timestamp': current_time,
                            'raw_data': raw_data_json,
                            'created_at': current_time
                        }
                        transformed_records.append(transformed_record)
        
        # 변환된 레코드에서 디바이스 정보 확인
        if transformed_records:
            sample_record = transformed_records[0]
            print(f"📋 변환된 레코드 샘플:")
            print(f"   센서 ID: {sample_record.get('sensor_company_id')}")
            print(f"   디바이스 ID: {sample_record.get('device_id')}")
            print(f"   디바이스명: {sample_record.get('device_name')}")
            print(f"   위치: ({sample_record.get('gps_location_lat')}, {sample_record.get('gps_location_lng')})")
        
        return transformed_records

    def save_to_supabase(self, records: List[Dict[str, Any]]) -> bool:
        """Supabase에 데이터 저장 (배치 처리 최적화)"""
        try:
            if not records:
                print("저장할 데이터가 없습니다.")
                return True
            
            print(f"💾 {len(records)}개 레코드 Supabase 저장 시작...")
            start_time = time.time()
            
            # 배치로 데이터 삽입 (Supabase는 한 번에 최대 1000개 레코드)
            batch_size = 1000
            total_saved = 0
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                try:
                    result = self.supabase.table(self.table_name).insert(batch).execute()
                    saved_count = len(result.data) if result.data else 0
                    total_saved += saved_count
                    print(f"   배치 {i//batch_size + 1} 저장 완료: {saved_count}개 레코드")
                except Exception as batch_error:
                    print(f"   ❌ 배치 {i//batch_size + 1} 저장 실패: {batch_error}")
                    # 개별 레코드로 재시도
                    for record in batch:
                        try:
                            result = self.supabase.table(self.table_name).insert([record]).execute()
                            if result.data:
                                total_saved += 1
                        except Exception as single_error:
                            print(f"     ❌ 개별 레코드 저장 실패: {single_error}")
                            print(f"     문제 레코드: {record.get('sensor_company_id', 'unknown')}")
            
            end_time = time.time()
            print(f"✅ 총 {total_saved}개 레코드 저장 완료 ({end_time - start_time:.1f}초)")
            return True
        except Exception as e:
            print(f"❌ Supabase 저장 오류: {e}")
            return False

def main():
    """메인 실행 함수 (최적화 버전)"""
    print("🌧️ Mertani 강우량 데이터 수집 및 Supabase 동기화 시작 (최적화 버전)")
    print("-" * 60)
    
    start_time = time.time()
    
    # 환경변수 확인
    email = os.getenv("MERTANI_USER_EMAIL")
    password = os.getenv("MERTANI_USER_PASSWORD")
    
    if not email or not password:
        print("❌ Mertani 로그인 정보가 설정되지 않았습니다.")
        return
    
    try:
        # 1. Mertani API 클라이언트 생성 및 로그인
        print("🔐 Mertani 로그인 중...")
        api = MertaniRainfallAPI()
        api.login(email, password)
        
        # 2. 센서 목록 확인 (캐시 활용)
        print("\n📡 센서 목록 확인 중...")
        sensors_with_device_info = api.get_all_rainfall_sensors_with_device_info()
        
        if not sensors_with_device_info:
            print("❌ 사용 가능한 센서가 없습니다.")
            return
        
        # 3. 병렬로 강우량 데이터 수집
        print("\n📡 강우량 데이터 병렬 수집 중...")
        rainfall_data = api.fetch_all_rainfall_data_parallel(days=1)
        
        # 4. Supabase 동기화
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            print("\n💾 Supabase 동기화 중...")
            supabase_sync = SupabaseSync()
            transformed_records = supabase_sync.transform_rainfall_data(rainfall_data, sensors_with_device_info)
            
            if transformed_records:
                success = supabase_sync.save_to_supabase(transformed_records)
                if success:
                    print("✅ 동기화 완료!")
                else:
                    print("❌ 동기화 실패!")
            else:
                print("⚠️ 변환된 데이터가 없습니다.")
        else:
            print("\n⚠️ Supabase 설정이 완료되지 않았습니다.")
        
        # 5. 요약 출력
        end_time = time.time()
        print("\n" + "="*60)
        print("📊 실행 요약")
        print("="*60)
        
        total_sensors = len(rainfall_data)
        success_count = sum(1 for d in rainfall_data.values() if d is not None)
        
        print(f"📡 총 센서: {total_sensors}개")
        print(f"✅ 성공: {success_count}개")
        print(f"❌ 실패: {total_sensors - success_count}개")
        print(f"⏱️ 총 실행 시간: {end_time - start_time:.1f}초")
        
        if os.getenv('GITHUB_ACTIONS'):
            print(f"🚀 GitHub Actions 환경에서 실행됨")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()
