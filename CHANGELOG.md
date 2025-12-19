# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- [UX] `UNIT_CD` 파라미터 자동 포맷팅 지원: 고수준 툴(`get_plenary_schedule`)에서 "22" 입력 시 "100022"로 자동 변환.
- [Docs] `call_api_raw` 도구 설명에 `UNIT_CD` 포맷(1000xx) 가이드 추가.
- [Test] `UNIT_CD` 변환 로직 및 Raw API 투명성 검증을 위한 테스트 코드 추가.

## [0.1.0] - 2025-03-19
### Added
- Initial release of AssemblyMCP (Beta).
- Core server implementation using FastMCP.
- Integration with Korean National Assembly Open API.
- Basic documentation (README, ARCHITECTURE, CONVENTIONS).
- CI pipeline configuration.
