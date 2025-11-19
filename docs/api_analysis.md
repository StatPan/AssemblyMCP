# 국회 OpenAPI 분석 및 MCP 설계 방안

## 1. 국회 OpenAPI 구조 분석

### 1.1 API 목록 구조
- **기본 URL**: https://open.assembly.go.kr/portal/openapi/
- **인증**: KEY 필수 (sample key로 테스트 가능)
- **포맷**: XML, JSON 지원
- **페이징**: pIndex, pSize 파라미터

### 1.2 API 카테고리 분류
1. **국회의원** - 국회의원 관련 정보
2. **의정활동별 공개** - 회의록, 의안, 위원회 등
3. **주제별 공개** - 특정 주제별 데이터
4. **보고서·발간물** - 각종 보고서 및 발간물
5. **국회 소속기관 제공 API** - 국회예산정책처 등

### 1.3 확인된 주요 API 목록

#### 의정활동별 공개 (1페이지에서 확인)
1. 회의록 대별 위원회 목록 (OU8JBT0015343C14378)
2. 법률안 제안이유 및 주요내용
3. 공청회 회의록
4. 예결산특별위원회 회의록
5. 의안별 회의록 목록
6. 회의별 의안목록
7. 회의별 안건목록
8. 시정조치 결과보고서 목록
9. 제안설명서 목록
10. 시청각자료 목록
11. 회의록별 상세정보
12. 소위원회 회의록

### 1.4 API 상세 스펙 예시 (회의록 대별 위원회 목록)
- **요청주소**: https://open.assembly.go.kr/portal/openapi/nkimylolanvseqagq
- **기본인자**: KEY, Type, pIndex, pSize
- **요청인자**: TH(대수), CLASS_ID(회의종류), CMIT_NM(위원회명)
- **출력값**: TH, CLASS_ID, CLASS_NM, CMIT_NM, CMIT_CD, SUB_CMIT_CD, SUB_CMIT_NM

## 2. 180개 API → 10개 미만 MCP 기능 통합 방안

### 2.1 MCP 기능 그룹화 전략

#### 그룹 1: 국회의원 정보 관리 (3개 API 통합)
- 국회의원 기본 정보
- 국회의원 활동 내역
- 국회의원 소속 위원회 정보

#### 그룹 2: 회의록 통합 검색 (4개 API 통합)
- 본회의 회의록
- 위원회 회의록
- 소위원회 회의록
- 공청회 회의록

#### 그룹 3: 의안 정보 관리 (3개 API 통합)
- 의안 기본 정보
- 의안 상세 내용
- 의안 처리 현황

#### 그룹 4: 위원회 운영 정보 (2개 API 통합)
- 위원회 기본 정보
- 위원회 회의 일정

#### 그룹 5: 법률안 분석 (2개 API 통합)
- 법률안 제안이유
- 법률안 주요내용

#### 그룹 6: 국회 문서 관리 (3개 API 통합)
- 제안설명서
- 시정조치 결과보고서
- 시청각자료

#### 그룹 7: 회의 안건 관리 (2개 API 통합)
- 회의별 안건목록
- 회의별 의안목록

#### 그룹 8: 국회 통계 정보 (2개 API 통합)
- 국회 활동 통계
- 의안 처리 통계

#### 그룹 9: 예산정책 정보 (2개 API 통합)
- 예결산 관련 정보
- 재정 통계 정보

#### 그룹 10: 검색 및 필터링 (모든 API 통합)
- 통합 검색 기능
- 다차원 필터링

### 2.2 MCP 기능 설계 상세

#### 기능 1: get_member_info()
- **통합 API**: 국회의원 관련 3개 API
- **파라미터**: member_id, name, committee, period
- **반환**: 국회의원 기본정보, 활동내역, 소속위원회

#### 기능 2: search_meeting_records()
- **통합 API**: 회의록 관련 4개 API
- **파라미터**: meeting_type, date_range, committee, keyword
- **반환**: 통합 회의록 정보

#### 기능 3: get_bill_info()
- **통합 API**: 의안 관련 3개 API
- **파라미터**: bill_id, bill_type, status, date_range
- **반환**: 의안 정보 및 처리 현황

#### 기능 4: get_committee_info()
- **통합 API**: 위원회 관련 2개 API
- **파라미터**: committee_id, committee_name, meeting_type
- **반환**: 위원회 정보 및 회의 일정

#### 기능 5: analyze_legislation()
- **통합 API**: 법률안 분석 2개 API
- **파라미터**: bill_id, analysis_type
- **반환**: 법률안 제안이유 및 주요내용

#### 기능 6: get_documents()
- **통합 API**: 문서 관리 3개 API
- **파라미터**: doc_type, date_range, keyword
- **반환**: 제안설명서, 보고서, 시청각자료

#### 기능 7: get_meeting_agenda()
- **통합 API**: 회의 안건 2개 API
- **파라미터**: meeting_id, date_range, committee
- **반환**: 회의 안건 및 의안 목록

#### 기능 8: get_statistics()
- **통합 API**: 통계 정보 2개 API
- **파라미터**: stat_type, period, category
- **반환**: 국회 활동 및 의안 처리 통계

#### 기능 9: get_budget_info()
- **통합 API**: 예산정책 2개 API
- **파라미터**: budget_type, fiscal_year, category
- **반환**: 예결산 및 재정 정보

#### 기능 10: comprehensive_search()
- **통합 API**: 모든 API 검색 기능
- **파라미터**: keyword, filters, sort_options
- **반환**: 통합 검색 결과

## 3. 구현 우선순위

### 1단계: 핵심 기능 (MVP)
1. get_member_info() - 국회의원 정보
2. search_meeting_records() - 회의록 검색
3. get_bill_info() - 의안 정보
4. get_committee_info() - 위원회 정보

### 2단계: 확장 기능
5. analyze_legislation() - 법률안 분석
6. get_meeting_agenda() - 회의 안건
7. comprehensive_search() - 통합 검색

### 3단계: 고급 기능
8. get_documents() - 문서 관리
9. get_statistics() - 통계 정보
10. get_budget_info() - 예산 정보

## 4. 기술적 고려사항

### 4.1 API 호출 최적화
- 병렬 호출 지원
- 캐싱 전략
- 에러 핸들링

### 4.2 데이터 표준화
- 통일된 응답 포맷
- 일관된 파라미터 명명
- 표준화된 에러 코드

### 4.3 성능 최적화
- 배치 처리
- 페이징 처리
- 데이터 압축

## 5. 다음 단계

1. **API 스펙 상세 분석**: 각 API의 상세 파라미터 및 응답 구조 분석
2. **MCP 인터페이스 설계**: FastMCP 기반의 인터페이스 정의
3. **프로토타입 구현**: MVP 기능 4개 구현
4. **테스트 및 검증**: 실제 API 호출 테스트
5. **문서화**: 사용자 가이드 및 API 문서 작성
